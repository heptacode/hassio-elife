from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ELifeCoordinator

_LOGGER = logging.getLogger(__name__)

PRESET_MODES = ["low", "middle", "high"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ELifeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ELifeVent(coordinator)])


class ELifeVent(CoordinatorEntity[ELifeCoordinator], FanEntity):
    _attr_has_entity_name = True
    _attr_name = "Vent"
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_vent"
        self._current_preset: str | None = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "e-Life",
            "manufacturer": "ELife",
            "model": "Smart e-Life",
        }

    @property
    def is_on(self) -> bool | None:
        vent = self.coordinator.data.get("vent")
        if vent is None:
            return None
        return vent.get("data", {}).get("status") == "on"

    @property
    def preset_mode(self) -> str | None:
        # Track locally; API only returns on/off status
        return self._current_preset if self.is_on else None

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        speed = preset_mode or self._current_preset or "high"
        await self.coordinator.client.control_vent(self.coordinator.vent_uid, "on", speed)
        self._current_preset = speed
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.control_vent(self.coordinator.vent_uid, "off")
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.client.control_vent(self.coordinator.vent_uid, "on", preset_mode)
        self._current_preset = preset_mode
        await self.coordinator.async_request_refresh()
