from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Self, cast, overload

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN

from ..const import (
    ATTR_CH_BLUE,
    ATTR_CH_CW,
    ATTR_CH_GREEN,
    ATTR_CH_RED,
    ATTR_CH_WW,
    ATTR_HUE,
    ATTR_REQUEUE,
    ATTR_SATURATION,
)


class _QueueingPolicy(StrEnum):
    BACK = "back"
    FRONT = "front"
    FRONT_RESET = "front_reset"
    SINGLE = "single"


@dataclass
class ColorCommandBase:
    speed_or_fade_duration: int | None = None
    use_speed: bool = False
    stay: int | None = None
    requeue: bool | None = None
    queueing_policy: _QueueingPolicy | None = None
    anim_name: str | None = None
    direction_long: bool | None = False  # True if long, False if short

    @classmethod
    def _gather_service_base_args(cls, service_attrs: dict[str, Any]) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if (val := service_attrs.get(ATTR_REQUEUE)) is not None:
            args["requeue"] = val
        return args


@dataclass
class ColorCommandHsv(ColorCommandBase):
    """Represents a single step in an animation sequence."""

    h: str | None = None
    s: str | None = None
    v: str | None = None
    ct: str | None = None

    @classmethod
    def from_service(cls, service_attrs: dict[str, Any]) -> Self:
        attrs = super()._gather_service_base_args(service_attrs)

        if (val := service_attrs.get(ATTR_HUE)) is not None:
            attrs["h"] = val

        if (val := service_attrs.get(ATTR_SATURATION)) is not None:
            attrs["s"] = val

        if (val := service_attrs.get(ATTR_BRIGHTNESS)) is not None:
            attrs["v"] = val

        if (val := service_attrs.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            attrs["ct"] = val

        return cls(**attrs)


@dataclass
class ColorCommandRgbww(ColorCommandBase):
    """Represents a single step in an animation sequence."""

    r: str | None = None
    g: str | None = None
    b: str | None = None
    cw: str | None = None
    ww: str | None = None

    @classmethod
    def from_service(cls, service_attrs: dict[str, Any]) -> Self:
        attrs = super()._gather_service_base_args(service_attrs)

        if (val := service_attrs.get(ATTR_CH_RED)) is not None:
            attrs["r"] = val

        if (val := service_attrs.get(ATTR_CH_GREEN)) is not None:
            attrs["g"] = val

        if (val := service_attrs.get(ATTR_CH_BLUE)) is not None:
            attrs["b"] = val

        if (val := service_attrs.get(ATTR_CH_CW)) is not None:
            attrs["cw"] = val

        if (val := service_attrs.get(ATTR_CH_WW)) is not None:
            attrs["ww"] = val

        return cls(**attrs)


class ChannelsType(StrEnum):
    HSV = "hsv"
    RGBWW = "rgbww"


@overload
def parse_color_cli_command(
    command_str: str, channels_type: Literal[ChannelsType.HSV]
) -> ColorCommandHsv: ...


@overload
def parse_color_cli_command(
    command_str: str, channels_type: Literal[ChannelsType.RGBWW]
) -> ColorCommandRgbww: ...


def parse_color_cli_command(
    command_str: str, channels_type: Literal[ChannelsType.RGBWW, ChannelsType.HSV]
) -> ColorCommandHsv | ColorCommandRgbww:
    cmd: ColorCommandHsv | ColorCommandRgbww | None = None
    match channels_type:
        case ChannelsType.HSV:
            cmd = ColorCommandHsv()
        case ChannelsType.RGBWW:
            cmd = ColorCommandRgbww()

    parts = command_str.split(" ")

    for p in parts:
        if "," in p:
            channels_parts = (
                p.split(",") + [None] * 5
            )  # pad with None to ensure at least 5 parts

            # replace empty strings with None
            channels_parts = [part if part != "" else None for part in channels_parts]

            match channels_type:
                case ChannelsType.HSV:
                    cmd = cast(ColorCommandHsv, cmd)
                    cmd.h, cmd.s, cmd.v, cmd.ct = channels_parts[
                        :4
                    ]  # take only first 4 parts
                case ChannelsType.RGBWW:
                    cmd = cast(ColorCommandRgbww, cmd)
                    cmd.r, cmd.g, cmd.b, cmd.cw, cmd.ww = channels_parts[
                        :5
                    ]  # take only first 5 parts
        else:
            is_fade_time_part = False
            if p.startswith("s") and p[1:].isdigit():
                is_fade_time_part = True
                cmd.use_speed = True
                p = p[1:]  # remove the 's' prefix

            if is_fade_time_part or p.isdigit():
                cmd.speed_or_fade_duration = float(p)
                if not cmd.use_speed:
                    cmd.speed_or_fade_duration *= (
                        1000  # convert seconds to milliseconds
                    )
            elif p.endswith("s") and p[:-1].isdigit():
                cmd.stay = float(p[:-1]) * 1000
            else:
                # Flags
                if ":" in p:
                    splits = p.split(":", 2)
                    cmd.anim_name = splits[1]
                    p = splits[0]

                if "r" in p:
                    cmd.requeue = True
                if "d" in p:
                    cmd.direction_long = True
                if "e" in p:
                    if cmd.queueing_policy is not None:
                        raise RuntimeError("cannot use multiple queuing policy flags")
                    cmd.queueing_policy = _QueueingPolicy.FRONT_RESET
                if "f" in p:
                    if cmd.queueing_policy is not None:
                        raise RuntimeError("cannot use multiple queuing policy flags")
                    cmd.queueing_policy = _QueueingPolicy.FRONT
                if "q" in p:
                    if cmd.queueing_policy is not None:
                        raise RuntimeError("cannot use multiple queuing policy flags")
                    cmd.queueing_policy = _QueueingPolicy.BACK
    return cmd


@overload
def parse_color_commands(
    commands: str, channels_type: Literal[ChannelsType.HSV]
) -> list[ColorCommandHsv]: ...


@overload
def parse_color_commands(
    commands: str, channels_type: Literal[ChannelsType.RGBWW]
) -> list[ColorCommandRgbww]: ...


def parse_color_commands(
    commands: str, channels_type: Literal[ChannelsType.RGBWW, ChannelsType.HSV]
) -> list[ColorCommandHsv] | list[ColorCommandRgbww]:
    return [parse_color_cli_command(x, channels_type) for x in commands.split(";")]


# --- Example Usage ---
if __name__ == "__main__":
    test_strings = [
        "+50,, 300 5000s",
        "124,5,12 5000",
        "120,80,100",
        ",,100 2000s",
        "-10,+20,-30 100 500s",
        "  10,20,30   600  700s  ",  # Test with extra whitespace
        "50,50,50",
        # Invalid cases
        "120,50",
        "120,50,60 abc",
        "",
        " , , ",  # This is valid: three empty strings
    ]

    print("--- Testing AnimCommand Parser ---")
    for test_str in test_strings:
        result = parse_color_cli_command(test_str, ChannelsType.HSV)
        print(f"Input: '{test_str}' -> Output: {result}")
