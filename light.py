from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import LightEntity
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
    async_add_entities(
        ELifeLight(coordinator, i, coordinator.light_uids[i])
        for i in range(len(coordinator.light_uids))
    )


class ELifeLight(CoordinatorEntity[ELifeCoordinator], LightEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ELifeCoordinator, room_no: int, uid: str) -> None:
        super().__init__(coordinator)
        self._room_no = room_no
        self._uid = uid
        self._attr_unique_id = f"{DOMAIN}_light_{room_no}"
        self._attr_name = f"Light {room_no}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "e-Life",
            "manufacturer": "ELife",
            "model": "Smart e-Life",
        }

    @property
    def is_on(self) -> bool | None:
        lights: list = self.coordinator.data.get("lights", [])
        if self._room_no >= len(lights) or lights[self._room_no] is None:
            return None
        return lights[self._room_no].get("data", {}).get("status") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.control_light(self._uid, "on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.control_light(self._uid, "off")
        await self.coordinator.async_request_refresh()
