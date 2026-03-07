from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ELifeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ELifeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ELifeElevatorButton(coordinator)])


class ELifeElevatorButton(CoordinatorEntity[ELifeCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Elevator Call"
    _attr_icon = "mdi:elevator"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_elevator"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "e-Life",
            "manufacturer": "ELife",
            "model": "Smart e-Life",
        }

    async def async_press(self) -> None:
        await self.coordinator.client.call_elevator(self.coordinator.elevator_uid)
