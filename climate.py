from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_HOME,
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

    def _optimistic_set(self, fields: dict) -> None:
        ac_list: list = self.coordinator.data.get("ac", [])
        if self._room_no < len(ac_list) and ac_list[self._room_no] is not None:
            ac_list[self._room_no].setdefault("data", {}).update(fields)
            self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.coordinator.client.control_ac(self._uid, "on", str(int(temp)))
        self._optimistic_set({"set_temp": str(int(temp)), "status": "on"})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        control = "off" if hvac_mode == HVACMode.OFF else "on"
        set_temp = str(int(self.target_temperature or 24))
        await self.coordinator.client.control_ac(self._uid, control, set_temp)
        _HA_TO_MODE = {v: k for k, v in _MODE_TO_HA.items()}
        fields: dict = {"status": control}
        if control == "on":
            fields["mode"] = _HA_TO_MODE.get(hvac_mode, "cool")
        self._optimistic_set(fields)


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
    _attr_preset_modes = [PRESET_HOME, PRESET_AWAY]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )

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

    @property
    def preset_mode(self) -> str | None:
        data = self._heat_data()
        if data is None:
            return None
        if data.get("mode") == "out":
            return PRESET_AWAY
        return PRESET_HOME

    def _optimistic_set(self, fields: dict) -> None:
        heat_list: list = self.coordinator.data.get("heat", [])
        if self._room_no < len(heat_list) and heat_list[self._room_no] is not None:
            heat_list[self._room_no].setdefault("data", {}).update(fields)
            self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self.coordinator.client.control_heat(self._uid, str(int(temp)))
        self._optimistic_set({"set_temp": str(int(temp))})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.control_heat(self._uid)
            self._optimistic_set({"status": "off"})
        else:
            set_temp = str(int(self.target_temperature or 24))
            await self.coordinator.client.control_heat(self._uid, set_temp)
            self._optimistic_set({"status": "on"})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        mode = "out" if preset_mode == PRESET_AWAY else "heat"
        await self.coordinator.client.set_heat_mode(self._uid, mode)
        self._optimistic_set({"mode": mode})
