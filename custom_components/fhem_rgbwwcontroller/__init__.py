"""The FHEM RGBWW Controller integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .core.rgbww_controller import RgbwwController

_logger = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR, Platform.UPDATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FHEM RGBWW Controller from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get Host from ConfigEntry
    host = entry.data[CONF_HOST]

    controller = RgbwwController(hass, host)
    await controller.connect()
    await controller.refresh()  # Ensure we can connect and get info before proceeding

    entry.runtime_data = controller

    # This forwards the setup to other platforms.
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Disconnect when the entry gets unloaded
    entry.async_on_unload(controller.disconnect)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This function is required for reloading and removing the integration.
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
