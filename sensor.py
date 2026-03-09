from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ELifeCoordinator

_LOGGER = logging.getLogger(__name__)

_DEVICE_INFO_TEMPLATE = {
    "name": "e-Life",
    "manufacturer": "ELife",
    "model": "Smart e-Life",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ELifeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Outdoor sensors
    entities += [
        ELifeOutdoorTemperature(coordinator),
        ELifeOutdoorPM10(coordinator),
        ELifeOutdoorPM25(coordinator),
    ]

    # Energy sensor
    entities.append(ELifeEnergySensor(coordinator))

    # Visitor sensors
    entities += [
        ELifeLastVisitorTime(coordinator),
        ELifeLastVisitorDoor(coordinator),
        ELifeLastVisitorType(coordinator),
    ]

    # EV charger sensor (only if configured)
    if coordinator.ev_room_key and coordinator.ev_user_key:
        entities.append(ELifeChargerSensor(coordinator))

    async_add_entities(entities)


def _device_info(coordinator: ELifeCoordinator) -> dict:
    return {"identifiers": {(DOMAIN, coordinator.entry_id)}, **_DEVICE_INFO_TEMPLATE}


# ---------------------------------------------------------------------------
# Outdoor weather / air quality
# ---------------------------------------------------------------------------

class ELifeOutdoorTemperature(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_outdoor_temp"
    _attr_name = "Outdoor Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data.get("climate_outdoor")
        if data is None:
            return None
        try:
            return float(data["data"]["weather"]["temp"])
        except (KeyError, TypeError, ValueError):
            return None


class ELifeOutdoorPM10(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_outdoor_pm10"
    _attr_name = "Outdoor PM10"
    _attr_device_class = SensorDeviceClass.PM10
    _attr_native_unit_of_measurement = "µg/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data.get("climate_outdoor")
        if data is None:
            return None
        try:
            return float(data["data"]["air"]["pm10value"])
        except (KeyError, TypeError, ValueError):
            return None


class ELifeOutdoorPM25(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_outdoor_pm25"
    _attr_name = "Outdoor PM2.5"
    _attr_device_class = SensorDeviceClass.PM25
    _attr_native_unit_of_measurement = "µg/m³"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data.get("climate_outdoor")
        if data is None:
            return None
        try:
            return float(data["data"]["air"]["pm25value"])
        except (KeyError, TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------

class ELifeEnergySensor(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_energy"
    _attr_name = "Energy"
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str | None:
        energy = self.coordinator.data.get("energy")
        if energy is None:
            return None
        # Return raw JSON as state; full data available via extra_state_attributes
        return "ok"

    @property
    def extra_state_attributes(self) -> dict | None:
        energy = self.coordinator.data.get("energy")
        if energy is None:
            return None
        return energy.get("data")


# ---------------------------------------------------------------------------
# Visitor log
# ---------------------------------------------------------------------------

def _visitor_list(coordinator: ELifeCoordinator) -> list:
    visitor = coordinator.data.get("visitor")
    if visitor is None:
        return []
    return visitor.get("data", {}).get("list", [])


class ELifeLastVisitorTime(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_last_visitor_time"
    _attr_name = "Last Visitor Time"
    _attr_icon = "mdi:doorbell"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str | None:
        lst = _visitor_list(self.coordinator)
        return lst[0]["reg_num"] if lst else None


class ELifeLastVisitorDoor(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_last_visitor_door"
    _attr_name = "Last Visitor Door"
    _attr_icon = "mdi:door"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str | None:
        lst = _visitor_list(self.coordinator)
        return lst[0]["door_type"] if lst else None


class ELifeLastVisitorType(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_last_visitor_type"
    _attr_name = "Last Visitor Type"
    _attr_icon = "mdi:account-question"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> str | None:
        lst = _visitor_list(self.coordinator)
        if not lst:
            return None
        return "호출" if lst[0]["call_type"] == "1" else "방범"


# ---------------------------------------------------------------------------
# EV Charger
# ---------------------------------------------------------------------------

class ELifeChargerSensor(CoordinatorEntity[ELifeCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_unique_id = f"{DOMAIN}_ev_charger"
    _attr_name = "EV Charger"
    _attr_icon = "mdi:ev-station"
    _attr_native_unit_of_measurement = "대"

    def __init__(self, coordinator: ELifeCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> int | None:
        charger = self.coordinator.data.get("charger")
        if charger is None:
            return None
        lst = charger.get("data", {}).get("list", [])
        return len(lst)

    @property
    def extra_state_attributes(self) -> dict | None:
        charger = self.coordinator.data.get("charger")
        if charger is None:
            return None
        return {"list": charger.get("data", {}).get("list", [])}
