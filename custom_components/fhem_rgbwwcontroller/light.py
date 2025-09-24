from typing import Any, cast

from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from .rgbww_controller import RgbwwController
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBWW_COLOR,
    ATTR_HS_COLOR,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)


# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import LightEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import voluptuous as vol

SERVICE_SET_HSV_ADV = "set_hsv_advanced"


def set_hsv_advanced(self, call: ServiceCall) -> None:
    print("hhlo")
    if call.data["hsv_command_string"] == "fade":
        print("as")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Abode light devices."""
    controller = cast(RgbwwController, entry.runtime_data)

    rgb = RgbwwLight(
        hass,
        controller,
        entry.unique_id,
        entry.title,
    )

    async_add_entities((rgb,))

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_HSV_ADV,
        {vol.Required("hsv_command_string"): cv.string},
        set_hsv_advanced,
    )


# we implement RgbwwStateUpdate but we cannot derive from here due to metaclass error
class RgbwwLight(LightEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    def __init__(
        self,
        hass: HomeAssistant,
        controller: RgbwwController,
        unique_id: str,
        name: str,
    ) -> None:
        """Initialize the light."""
        super().__init__()
        self._hass = hass
        self._attr_unique_id = unique_id + "_light"
        self._attr_name = name + " Light"

        self._attr_supported_color_modes = (
            ColorMode.HS,
            ColorMode.RGBWW,
            ColorMode.COLOR_TEMP,
        )
        self._attr_supported_features = LightEntityFeature.TRANSITION
        self._attr_color_mode = {ColorMode.HS}

        self._attr_available = controller.connected

        self._controller = controller

        # --- ENTITY AND DEVICE LINKING ---
        # This is where the magic happens.
        self._attr_unique_id = f"{unique_id}_lightunique"
        self._attr_name = f"{name}"  # "light" prefix will be added automatically

        # This `device_info` block links the entity to the device you created
        # in __init__.py. The `identifiers` MUST match exactly.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
        )
        # --- END LINKING ---

    async def async_added_to_hass(self) -> None:
        self._controller.register_callback(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from the events."""
        self._controller.unregister_callback(self)

        await super().async_will_remove_from_hass()

    def on_update_hsv(self, h: int | None, s: int | None, v: int | None) -> None:
        if h is not None:
            self._attr_hs_color = (h, s)

        if v is not None:
            self._attr_brightness = (v / 100.0) * 255

        self._attr_is_on = v > 0

        self.async_write_ha_state()

    # protocol rgbww state
    def on_connection_update(self, connected: bool) -> None:
        self._attr_available = connected

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if (rgbww := kwargs.get(ATTR_RGBWW_COLOR)) is not None:
            await self._controller.set_raw(*rgbww)
        elif (hs := kwargs.get(ATTR_HS_COLOR)) is not None:
            self._attr_color_mode = ColorMode.HS
            args = {"hue": hs[0], "saturation": hs[1]}
            if "transition" in kwargs:
                args["t"] = float(kwargs["transition"])
            await self._controller.set_hsv(**args)
        elif (ct := kwargs.get(ATTR_COLOR_TEMP_KELVIN)) is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            await self._controller.set_hsv(ct=ct)
        elif (rgbww := kwargs.get(ATTR_RGBWW_COLOR)) is not None:
            self._attr_color_mode = ColorMode.RGBWW
            # Call your API's raw mode function
        else:
            await self._controller.set_hsv(brightness=100)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._controller.set_hsv(brightness=0)

    def on_transition_finished(self, name: str, requeued: bool) -> None:
        event_data = {
            "device_id": "rgbwwid",
            "type": "transition_finished",
            "name": name,
            "requeued": requeued,
        }
        self._hass.bus.async_fire("transition_finished", event_data)


# class MyReceiver(RgbwwStateUpdate):
#    def __init__(self, light: RgbwwLight):
#        self._light = light
#
#    def on_update_hsv(self, h: int | None, s: int | None, v: int | None) -> None:
#        if h is not None:
#            self._light._attr_hs_color = (h, s)
#
#        if v is not None:
#            self._light._attr_brightness = (v / 100.0) * 255
#
#        self._light._attr_is_on = v > 0
#
#        self._light.async_write_ha_state()
#
#    def on_connection_update(self, connected: bool) -> None:
#        self._light._attr_available = connected
#
#        self._light.async_write_ha_state()
