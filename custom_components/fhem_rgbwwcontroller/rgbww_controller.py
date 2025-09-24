# noqa: D102
from dataclasses import dataclass
from datetime import timedelta
import enum
import httpx
import asyncio
import json
from typing import Literal, Protocol

import logging

_logger = logging.getLogger(__name__)


class _HttpMethod(enum.Enum):
    GET = enum.auto()
    POST = enum.auto()


class RgbwwStateUpdate(Protocol):
    def on_update_hsv(h: int | None, s: int | None, v: int | None) -> None: ...
    def on_connection_update(connected: bool) -> None: ...
    def on_animation_finished(connected: bool) -> None: ...
    def on_sync_status(connected: bool) -> None: ...


class RgbwwReceiver(Protocol):
    def on_json_message(self, json_msg: dict) -> None:
        pass

    def on_connect_status_change(self, connected: bool) -> None:
        pass


class _TcpReceiver(asyncio.Protocol):
    def __init__(
        self,
        host: str,
        sink: RgbwwReceiver,
        on_con_lost: asyncio.Future,
    ) -> None:
        self._sink = sink
        self.on_con_lost = on_con_lost
        self._host = host

        self._buffer = ""
        self._transport: asyncio.Transport | None = None

    def connection_made(self, transport):
        _logger.error("%s - Connection established", self._host)
        self._sink.on_connect_status_change(True)

    def _consume_json_msg(self) -> dict | None:
        try:
            # Try to decode an object from the current position
            decoder = json.JSONDecoder()
            json_obj, end_pos = decoder.raw_decode(self._buffer)

            self._buffer = self._buffer[end_pos:]
            # If successful, process the message
            return json_obj
        except json.JSONDecodeError:
            # Not a complete JSON object yet, break and wait for more data
            return None

    def data_received(self, data):
        self._buffer += data.decode("utf-8")

        while (json_msg := self._consume_json_msg()) is not None:
            self._sink.on_json_message(json_msg)

    def connection_lost(self, exc):
        _logger.error("%s - Connection lost: %s", self._host, exc)
        self._sink.on_connect_status_change(False)
        self.on_con_lost.set_result(True)
        self._buffer = ""


@dataclass
class _State:
    color_temp: int
    hue: int
    saturation: int
    brightness: int
    color_mode: Literal["raw", "hsv"]
    raw_r: int
    raw_g: int
    raw_b: int
    raw_ww: int
    raw_cw: int


class RgbwwController(RgbwwReceiver):
    """The actual binding to the controller via network."""

    _TCP_PORT = 9090
    TIMEOUT = 70

    def __init__(self, host: str) -> None:
        self._host = host
        self._connected = False
        self.state = _State(0, 0, 0, 0, "raw", 0, 0, 0, 0, 0)
        self._connection_task: asyncio.Task | None = None

        self._on_con_lost: asyncio.Future | None = None
        self._on_con_established: asyncio.Future | None = None
        self._callbacks: list[RgbwwStateUpdate] = []
        self._transport: asyncio.Transport | None = None
        self._watchdog_handle: asyncio.TimerHandle | None = None

    def _reset_watchdog(self):
        """Resets or starts the connection watchdog."""
        # Cancel the old timer if it exists
        if self._watchdog_handle:
            self._watchdog_handle.cancel()

        # Schedule the timeout_occurred method to be called after TIMEOUT seconds
        loop = asyncio.get_running_loop()
        self._watchdog_handle = loop.call_later(
            RgbwwController.TIMEOUT, self._timeout_occurred
        )

    async def _run_connection_task(self):
        """Connect to the device and keep connection alive in the event of a connection loss."""
        while True:
            try:
                loop = asyncio.get_running_loop()
                self._on_con_lost = loop.create_future()
                self._on_con_established = loop.create_future()

                self._transport, _ = await loop.create_connection(
                    lambda: _TcpReceiver(
                        self._host,
                        self,
                        self._on_con_lost,
                    ),
                    self._host,
                    RgbwwController._TCP_PORT,
                )
                # Most of the time, the task will be waiting here
                await self._on_con_lost
            except Exception as e:
                _logger.error("%s - Connection error: %s", self._host, e)
            await asyncio.sleep(60)

    def register_callback(self, rcv: RgbwwStateUpdate) -> None:
        """Register a callback object."""
        if rcv in self._callbacks:
            raise ValueError("Already registered")

        self._callbacks.append(rcv)

    def unregister_callback(self, rcv: RgbwwStateUpdate) -> None:
        """Un-Register a callback object."""
        if rcv not in self._callbacks:
            raise ValueError("Receiver not registered")

        self._callbacks.remove(rcv)

    def on_connect_status_change(self, connected: bool) -> None:
        if connected:
            self._on_con_established.set_result(None)
            self._reset_watchdog()
        else:
            self._watchdog_handle.cancel()
            self._watchdog_handle = None
            self._transport = None

        self._connected = connected
        for x in self._callbacks:
            x.on_connection_update(connected)

    async def connect(self) -> None:
        """Connect to the controller (including reconnects)."""
        if self._connection_task is not None:
            return  # Connection task already running

        self._connection_task = asyncio.create_task(
            self._run_connection_task(), name="fhem_rgbwwcontroller_connection"
        )

    async def connect_wait_for_connection(
        self, timeout: timedelta = timedelta(seconds=10)
    ) -> None:
        """Connect to the controller (including reconnects)."""
        self.connect()
        await asyncio.wait_for(self._on_con_established, timeout)

    async def disconnect(self):
        if self._transport is None:
            return

        _logger.error("%s - Disconnecting", self._host)
        self._connection_task.cancel()
        self._transport.close()

    def _timeout_occurred(self):
        _logger.warning(
            "%s - ❌ Watchdog timeout! No message received for %s seconds. Closing the connection.",
            self._host,
            RgbwwController.TIMEOUT,
        )

    async def set_hsv(
        self,
        hue: int | None = None,
        saturation: int | None = None,
        brightness: int | None = None,
        t: float | None = None,
        ct: int | None = None,
    ) -> None:
        # data = {
        #    "hsv": {"h": 100, "s": 100, "v": 100, "ct": 2700},
        #    "cmd": "",  # transition type
        #    "t": 2.0,  # fade time
        #    "s": 1.0,  # fade speed
        #    "q": 1,
        # }
        data: dict[str, any] = {"hsv": {}}

        if hue is not None:
            data["hsv"]["h"] = hue

        if brightness is not None:
            data["hsv"]["v"] = brightness

        if saturation is not None:
            data["hsv"]["s"] = saturation

        if ct is not None:
            data["hsv"]["ct"] = ct

        if t is not None:
            data["t"] = t

        await self._send_http_post("color", data)

    async def set_raw(
        self,
        r: int | None = None,
        g: int | None = None,
        b: int | None = None,
        cw: int | None = None,
        ww: int | None = None,
    ) -> None:
        data: dict[str, any] = {"raw": {}}

        if r is not None:
            data["raw"]["r"] = r

        if g is not None:
            data["raw"]["g"] = g

        if b is not None:
            data["raw"]["b"] = b

        if cw is not None:
            data["raw"]["cw"] = cw

        if ww is not None:
            data["raw"]["ww"] = ww

        await self._send_http_post("color", data)

    @property
    def connected(self):
        return self._connected

    def on_json_message(self, json_msg: dict) -> None:
        # ANY data from the server resets the timer.
        self._reset_watchdog()

        match json_msg["method"]:
            case "color_event":
                if "hsv" in json_msg["params"]:
                    self.state.hue = json_msg["params"]["hsv"]["h"]
                    self.state.saturation = json_msg["params"]["hsv"]["s"]
                    self.state.color_temp = json_msg["params"]["hsv"]["ct"]
                    self.state.brightness = json_msg["params"]["hsv"]["v"]

                if "raw" in json_msg["params"]:
                    self.state.raw_ww = json_msg["params"]["raw"]["ww"]
                    self.state.raw_cw = json_msg["params"]["raw"]["cw"]
                    self.state.raw_r = json_msg["params"]["raw"]["r"]
                    self.state.raw_g = json_msg["params"]["raw"]["g"]
                    self.state.raw_b = json_msg["params"]["raw"]["b"]

                self.state.color_mode = json_msg["params"]["mode"]
                print(f"{self._host} - {self.state}")

                for x in self._callbacks:
                    x.on_update_hsv(
                        self.state.hue, self.state.saturation, self.state.brightness
                    )
            # my $colorMode = "raw";
            # if ( exists $obj->{params}->{hsv} ) {
            #    $colorMode = "hsv";
            #    EspLedController_UpdateReadingsHsv( $hash, $obj->{params}{hsv}{h}, $obj->{params}{hsv}{s}, $obj->{params}{hsv}{v}, $obj->{params}{hsv}{ct} );
            # }
            # EspLedController_UpdateReadingsRaw( $hash, $obj->{params}{raw}{r}, $obj->{params}{raw}{g}, $obj->{params}{raw}{b}, $obj->{params}{raw}{cw}, $obj->{params}{raw}{ww} );
            # readingsSingleUpdate( $hash, 'colorMode', $colorMode, 1 );
            # }

            case "transition_finished":
                ...
            # elsif ( $obj->{method} eq "transition_finished" ) {
            # my $msg = $obj->{params}{name} . "," . ($obj->{params}{requeued} ? "requeued" : "finished");
            # readingsSingleUpdate( $hash, "tranisitionFinished", $msg, 1 );
            # }
            case "keep_alive":
                ...
            # elsif ( $obj->{method} eq "keep_alive" ) {
            # Log3( $hash, 4, "$hash->{NAME}: EspLedController_Read: keep_alive received" );
            # $hash->{LAST_RECV} = $now;
            # }
            case "clock_slave_status":
                ...
            # elsif ( $obj->{method} eq "clock_slave_status" ) {
            # readingsBeginUpdate($hash);
            # readingsBulkUpdate( $hash, 'clockSlaveOffset',     $obj->{params}{offset} );
            # readingsBulkUpdate( $hash, 'clockCurrentInterval', $obj->{params}{current_interval} );
            # readingsEndUpdate( $hash, 1 );
            # }
            case _:
                ...
            # else {
            # Log3( $name, 3, "$hash->{NAME}: EspLedController_ProcessRead: Unknown message type: " . $obj->{method} );
            # }

    async def get_info(self) -> dict:
        json_data = await self._send_http_get("info")
        return json.loads(json_data)

    async def _send_http_post(self, endpoint: str, payload: dict[str, any]) -> None:
        headers = {
            "user-agent": "homeassistant-fhem_rgbwwcontroller",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"http://{self._host}/{endpoint}",
                json=payload,
                headers=headers,
            )

            r.raise_for_status()

    async def _send_http_get(self, endpoint: str) -> str:
        headers = {
            "user-agent": "homeassistant-fhem_rgbwwcontroller",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"http://{self._host}/{endpoint}",
                headers=headers,
            )

            r.raise_for_status()

            return r.text


async def main():
    a = RgbwwController("192.168.2.53")
    info = await a.get_info()
    await a.connect()

    await a.set_hsv(brightness=100)

    await asyncio.sleep(120)


if __name__ == "__main__":
    asyncio.run(main())
