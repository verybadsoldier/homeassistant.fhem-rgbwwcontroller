from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN  # It's good practice to have a const.py for your domain


class MyControllerBaseEntity(Entity):
    """A base class for all My RGBWW Controller entities."""

    _attr_has_entity_name = True

    def __init__(self, device_id: str, mac_address: str) -> None:
        """Initialize the base entity."""
        self._device_id = device_id

        # ✅ Define DeviceInfo once in this central location
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="My Awesome RGBWW Controller",
            manufacturer="Your Name Here",
            model="RGBWW WiFi Controller v2",
            sw_version="1.0",
            connections={("mac", mac_address)} if mac_address else None,
        )
