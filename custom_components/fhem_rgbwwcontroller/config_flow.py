"""Config flow for the FHEM RGBWW Controller integration."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Any

from httpx import HTTPError
import voluptuous as vol

from config.custom_components.fhem_rgbwwcontroller.rgbww_controller import (
    RgbwwController,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import TextSelector, selector

from . import controller_autodetect
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
    }
)


class RgbwwConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FHEM RGBWW Controller."""

    VERSION = 1

    def __init__(self):
        super().__init__()
        self._scan_tasks: list[asyncio.Task] | None = None
        self._scan_monitor_task: asyncio.TaskGroup | None = None
        self._scan_network: ipaddress.IPv4Network | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=["scan_form", "manual"],
        )

    async def async_step_scan_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="scan_start",
            data_schema=vol.Schema(
                {
                    vol.Required("ip_range", default="192.168.2.0/24"): TextSelector(),
                }
            ),
            errors={},
        )

    async def _monitor_progress(self):
        """Monitors the progress of the tasks and updates the progress bar."""
        while True:
            num_done_tasks = len([x for x in self._scan_tasks if x.done()])

            if num_done_tasks < len(self._scan_tasks):
               self.async_update_progress(num_done_tasks / float(len(self._scan_tasks)))
            else:
                break

            # Wait for one second before the next update
            await asyncio.sleep(1)

        # Await all tasks to ensure they are fully completed
        await asyncio.gather(*self._scan_tasks)

    async def async_step_scan_start(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._scan_tasks is None:
            self._scan_network = ipaddress.IPv4Network(user_input["ip_range"])
            self._scan_tasks = [asyncio.create_task(x) for x in controller_autodetect.scan_dummy(self._scan_network)]

            self._scan_monitor_task = self.hass.async_create_task(self._monitor_progress())

            return self.async_show_progress(
                progress_action="scanning",
                progress_task=self._scan_monitor_task,
            )
        else:
            return self.async_show_progress_done(next_step_id="scan_finished")

    async def async_step_scan_finished(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        found_controllers = [t.result() for t in self._scan_tasks if t.result() is not None]

        if not found_controllers:
            return self.async_abort("scan_no_controllers", description_placeholders={"network": str(self._scan_network)})

        controller_names = [f"{x.info['name']} ({x.host})" for x in found_controllers]

        data_schema = vol.Schema({vol.Required(CONF_NAME): str,
                                  vol.Required(CONF_HOST): selector({
                                    "select": {
                                        "options": controller_names,
                                    }
                                })})

        return self.async_show_form(
            step_id="finalize",
            data_schema=data_schema,
            errors={},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        data_schema = vol.Schema({vol.Required(CONF_NAME): str,
                                  vol.Required(CONF_HOST): str})

        return self.async_show_form(
            step_id="finalize",
            data_schema=data_schema,
            errors={},
        )

    async def async_step_finalize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)


    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        cur_data = self._get_reconfigure_entry().data
        errors: dict[str, str] = {}
        if user_input:
            host = user_input[CONF_HOST]
            controller = RgbwwController(host)
            try:
                # just check if reachable
                _ = await controller.get_info()
            except HTTPError:
                errors[CONF_HOST] = f"Cannot retrieve MAC address from host {host}"
                cur_data = user_input
            else:
                # to support the scenario that a physical device has been replaced by another device
                # we don't change the unique_id and we allow it to differ from the MAC
                # mac = info["connection"]["mac"]
                # await self.async_set_unique_id(mac)
                # self._abort_if_unique_id_mismatch(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                    reason="Host changed successfully.",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=cur_data[CONF_HOST]
                    ): TextSelector(),
                }
            ),
            errors=errors,
        )


from homeassistant.config_entries import OptionsFlowWithReload

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("show_things"): bool,
    }
)


class RgbwwFlowHandler(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_menu(
            step_id="user",
            menu_options=["Add one controller", "Scan network for controllers"],
            description_placeholders={
                "model": "Example model",
            },
        )
