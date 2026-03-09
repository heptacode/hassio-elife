from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ELifeCoordinator

_LOGGER = logging.getLogger(__name__)

# ELIFE API mode string → HA HVACMode
_MODE_TO_HA: dict[str, HVACMode] = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "auto": HVACMode.AUTO,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ELifeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ClimateEntity] = [
        ELifeAC(coordinator, i, coordinator.ac_uids[i])
        for i in range(len(coordinator.ac_uids))
    ]
    entities += [
        ELifeHeat(coordinator, i, coordinator.heat_uids[i])
        for i in range(len(coordinator.heat_uids))
    ]

    async_add_entities(entities)


class ELifeAC(CoordinatorEntity[ELifeCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: ELifeCoordinator, room_no: int, uid: str) -> None:
        super().__init__(coordinator)
        self._room_no = room_no
        self._uid = uid
        self._attr_unique_id = f"{DOMAIN}_ac_{room_no}"
        self._attr_name = f"AC {room_no}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "e-Life",
            "manufacturer": "ELife",
            "model": "Smart e-Life",
        }

    def _ac_data(self) -> dict | None:
        ac_list: list = self.coordinator.data.get("ac", [])
        if self._room_no >= len(ac_list) or ac_list[self._room_no] is None:
            return None
        return ac_list[self._room_no].get("data")

    @property
    def hvac_mode(self) -> HVACMode | None:
        data = self._ac_data()
        if data is None:
            return None
        if data.get("status") == "off":
            return HVACMode.OFF
        return _MODE_TO_HA.get(data.get("mode", ""), HVACMode.COOL)

    @property
    def current_temperature(self) -> float | None:
        data = self._ac_data()
        if data is None:
            return None
        try:
            return float(data["current_temp"])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        data = self._ac_data()
        if data is None:
            return None
        try:
            return float(data["set_temp"])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.coordinator.client.control_ac(self._uid, "on", str(int(temp)))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        control = "off" if hvac_mode == HVACMode.OFF else "on"
        set_temp = str(int(self.target_temperature or 24))
        await self.coordinator.client.control_ac(self._uid, control, set_temp)
        await self.coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Ondol floor heating
# ---------------------------------------------------------------------------

class ELifeHeat(CoordinatorEntity[ELifeCoordinator], ClimateEntity):
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 5.0
    _attr_max_temp = 40.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator: ELifeCoordinator, room_no: int, uid: str) -> None:
        super().__init__(coordinator)
        self._room_no = room_no
        self._uid = uid
        self._attr_unique_id = f"{DOMAIN}_heat_{room_no}"
        self._attr_name = f"Heat {room_no}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "e-Life",
            "manufacturer": "ELife",
            "model": "Smart e-Life",
        }

    def _heat_data(self) -> dict | None:
        heat_list: list = self.coordinator.data.get("heat", [])
        if self._room_no >= len(heat_list) or heat_list[self._room_no] is None:
            return None
        return heat_list[self._room_no].get("data")

    @property
    def hvac_mode(self) -> HVACMode | None:
        data = self._heat_data()
        if data is None:
            return None
        if data.get("status") == "off":
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        data = self._heat_data()
        if data is None:
            return None
        try:
            return float(data["current_temp"])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def target_temperature(self) -> float | None:
        data = self._heat_data()
        if data is None:
            return None
        try:
            return float(data["set_temp"])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.coordinator.client.control_heat(self._uid, str(int(temp)))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.control_heat(self._uid)
        else:
            set_temp = str(int(self.target_temperature or 24))
            await self.coordinator.client.control_heat(self._uid, set_temp)
        await self.coordinator.async_request_refresh()
