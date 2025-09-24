"""Config flow for the FHEM RGBWW Controller integration."""

from __future__ import annotations

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            controller = RgbwwController(host)

            try:
                info = await controller.get_info()

                # the unique_id will not be matching the device MAC anymore
                # after replacing the device as the unique_id won't be updated
                mac = info["connection"]["mac"]
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(f"Controller with MAC '{mac}'")

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except HTTPError:
                errors[CONF_HOST] = f"Cannot retrieve MAC address from host {host}"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

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
