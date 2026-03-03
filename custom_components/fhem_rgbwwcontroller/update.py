"""Update platform for FHEM RGBWW Controller."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .core.rgbww_controller import RgbwwController

_logger = logging.getLogger(__name__)

# Default URL in case the config is empty
DEFAULT_OTA_URL = "http://rgbww.dronezone.de/testing/version.json"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Update entity from a config entry."""
    controller: RgbwwController = hass.data[DOMAIN][entry.entry_id]

    # Create the coordinator that periodically checks the external version.json
    coordinator = RgbwwFirmwareCoordinator(hass, controller)
    
    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([RgbwwFirmwareUpdateEntity(coordinator, controller)])


class RgbwwFirmwareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching the remote version.json periodically."""

    def __init__(self, hass: HomeAssistant, controller: RgbwwController) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _logger,
            name=f"{controller.device_name} Firmware Check",
            # Only check twice a day to save server resources and avoid rate limits
            update_interval=timedelta(hours=12), 
        )
        self.controller = controller

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest firmware data from the configured OTA URL."""
        # Read the URL from the controller config (matching the firmware's behavior)
        ota_url = self.controller.config.get("general", {}).get("otaurl", DEFAULT_OTA_URL)
        
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(ota_url) as response:
                response.raise_for_status()
                return await response.json()
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with OTA server: {err}") from err


class RgbwwFirmwareUpdateEntity(CoordinatorEntity[RgbwwFirmwareCoordinator], UpdateEntity):
    """Representation of a Firmware Update entity."""

    _attr_has_entity_name = True
    _attr_name = "Firmware Update"
    
    # Enables the "Install" button in the UI and supports the in_progress property
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    def __init__(
        self, coordinator: RgbwwFirmwareCoordinator, controller: RgbwwController
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self.controller = controller
        
        mac = controller.info["connection"]["mac"]
        self._attr_unique_id = f"{mac}_update"
        
        # TODO: Link your device_info here so the entity is grouped under the device
        # self._attr_device_info = ... 

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        # Retrieved from the device info fetch
        return self.controller.info.get("git_version")

    @property
    def latest_version(self) -> str | None:
        """Return the latest available version."""
        if self.coordinator.data:
            return self.coordinator.data.get("rom", {}).get("fw_version")
        return None

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        update_payload = self.coordinator.data
        if not update_payload:
            raise HomeAssistantError("Cannot start update: No version data available.")

        _logger.info("Starting firmware update for %s", self.controller.host)
        
        try:
            # 1. Trigger the update by POSTing the version.json payload
            await self.controller.async_trigger_ota_update(update_payload)
            
            # 2. Polling loop for the status (non-blocking due to asyncio.sleep)
            status = 1  # 1 = OTA_PROCESSING
            self._attr_in_progress = True
            
            # Wait a maximum of 300 seconds (matching the FHEM script logic)
            timeout_counter = 0 
            
            while status == 1 and timeout_counter < 150: 
                # Update UI to show that the installation is actively progressing
                self.async_write_ha_state() 
                await asyncio.sleep(2)
                timeout_counter += 1
                
                status_res = await self.controller.async_get_ota_status()
                status = status_res.get("status", 0)

            self._attr_in_progress = False

            # 3. Evaluate the final status
            if status == 2:
                _logger.info("Firmware update successful. Restarting %s", self.controller.host)
                await self.controller.async_restart_device()
                
                # Short pause, then reload data so the new version appears in the UI
                await asyncio.sleep(5)
                await self.controller.refresh()
                self.async_write_ha_state()
            elif status == 4:
                raise HomeAssistantError("Firmware update failed on the device.")
            elif status == 1:
                raise HomeAssistantError("Firmware update timed out.")

        except Exception as err:
            self._attr_in_progress = False
            _logger.error("Error during OTA update: %s", err)
            raise HomeAssistantError(f"OTA update failed: {err}") from err