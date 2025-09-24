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
from homeassistant.helpers.selector import TextSelector

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

    def _show_menu(self) -> ConfigFlowResult:
        """Show the initial menu."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["scan_form", "manual"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user confirmation step."""
        # Abort if an instance is already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # If user_input is not None, the user has clicked "Submit"
        if user_input is not None:
            # Create the config entry with an empty title and data
            return self.async_create_entry(title="My Simple Integration", data={})

        # Show the confirmation form to the user
        # The description will be pulled from strings.json
        return self._show_menu()

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

        # Find results if needed
        return [t.result() for t in self._scan_tasks if t.result() is not None]

        # Store results or move to the next step
        self.data["results"] = results
        self.hass.async_create_task(self.hass.config_entries.async_continue_flow(
            self.flow_context["flow_id"],
            "scan_finished"
        ))

    async def async_step_scan_start(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._scan_tasks is None:
            network = ipaddress.IPv4Network(user_input["ip_range"])
            self._scan_tasks = [asyncio.create_task(x) for x in controller_autodetect.scan_dummy(network)]


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
        if not user_input:
            return self.async_show_form(step_id="finish")
        return self.async_create_entry(title="Some title", data={})

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
