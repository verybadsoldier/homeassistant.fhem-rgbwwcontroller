from typing import Any
from .rgbww_controller import (
    RgbwwController,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBWW_COLOR,
    ATTR_HS_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)

import voluptuous as vol

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import ATTR_BRIGHTNESS, PLATFORM_SCHEMA, LightEntity
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Abode light devices."""

    async_add_entities(
        (
            RgbwwLight(
                "id." + entry.data[CONF_NAME],
                entry.data[CONF_NAME],
                entry.data[CONF_HOST],
            ),
        )
    )


class RgbwwLight(LightEntity):
    """Representation of a demo light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    def __init__(self, unique_id: str, device_name: str, host: str) -> None:
        """Initialize the light."""
        super().__init__()
        self._host = host

        self._attr_supported_color_modes = (ColorMode.XY,)
        self._attr_supported_features = LightEntityFeature.TRANSITION
        self._attr_color_mode = ColorMode.HS
        self._controller = RgbwwController(self._host)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if (rgbww := kwargs.get(ATTR_RGBWW_COLOR)) is not None:
            await self._controller.set_raw(*rgbww)
        elif (hs := kwargs.get(ATTR_HS_COLOR)) is not None:
            await self._controller.set_hsv(hue=hs[0], saturation=hs[1])
        elif (brightness := kwargs.get("brightness")) is not None:
            await self._controller.set_hsv(brightness=(brightness / 255) * 100)
        else:
            await self._controller.set_hsv(brightness=100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._controller.set_hsv(brightness=0)
