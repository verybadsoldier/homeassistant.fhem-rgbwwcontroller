"""The FHEM RGBWW Controller integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

_PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the FHEM RGBWW Controller component."""
    # This function is the initial entry point. For a UI-only integration,
    # it simply needs to return True to signal that the component is loaded and ready.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FHEM RGBWW Controller from a config entry."""
    # Your TODOs for creating and storing an API instance are correct.
    # This is where you would connect to your device.
    # For now, we'll assume no connection is needed for testing.
    # entry.runtime_data = MyAPI(...)

    # This forwards the setup to your light.py file.
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This function is required for reloading and removing the integration.
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
