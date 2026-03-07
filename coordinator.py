from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import ELifeAPIClient, ELifeAuthError
from .const import (
    CONF_AC_UIDS,
    CONF_DEVICE_UUID,
    CONF_ELEVATOR_UID,
    CONF_EV_ROOM_KEY,
    CONF_EV_USER_KEY,
    CONF_HEAT_UIDS,
    CONF_LIGHT_UIDS,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VENT_UID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ELifeCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._entry = entry

        self.ac_uids: list[str]    = json.loads(entry.data[CONF_AC_UIDS])
        self.light_uids: list[str] = json.loads(entry.data[CONF_LIGHT_UIDS])
        self.heat_uids: list[str]  = json.loads(entry.data[CONF_HEAT_UIDS])
        self.vent_uid: str         = entry.data[CONF_VENT_UID]
        self.elevator_uid: str     = entry.data[CONF_ELEVATOR_UID]
        self.ev_room_key: str      = entry.data.get(CONF_EV_ROOM_KEY, "")
        self.ev_user_key: str      = entry.data.get(CONF_EV_USER_KEY, "")

        self.client = ELifeAPIClient(
            hass=hass,
            session=async_get_clientsession(hass),
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            device_uuid=entry.data[CONF_DEVICE_UUID],
        )

    @property
    def entry_id(self) -> str:
        return self._entry.entry_id

    async def _async_update_data(self) -> dict:
        try:
            async with asyncio.timeout(60):
                return await self._fetch_all()
        except ELifeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout fetching ELife data") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching ELife data: {err}") from err

    async def _fetch_all(self) -> dict:
        data: dict = {}

        # Fetch AC, light, heat in parallel (each group is also parallel internally)
        ac_results, light_results, heat_results = await asyncio.gather(
            asyncio.gather(
                *(self.client.get_ac_status(uid) for uid in self.ac_uids),
                return_exceptions=True,
            ),
            asyncio.gather(
                *(self.client.get_light_status(uid) for uid in self.light_uids),
                return_exceptions=True,
            ),
            asyncio.gather(
                *(self.client.get_heat_status(uid) for uid in self.heat_uids),
                return_exceptions=True,
            ),
        )

        data["ac"]     = [r if not isinstance(r, Exception) else None for r in ac_results]
        data["lights"] = [r if not isinstance(r, Exception) else None for r in light_results]
        data["heat"]   = [r if not isinstance(r, Exception) else None for r in heat_results]

        # Build remaining coroutines dynamically
        coros = [
            self.client.get_vent_status(self.vent_uid),
            self.client.get_outdoor_climate(),
            self.client.get_energy(),
            self.client.get_visitor(),
        ]
        keys = ["vent", "climate_outdoor", "energy", "visitor"]

        if self.ev_room_key and self.ev_user_key:
            coros.append(self.client.get_charger(self.ev_room_key, self.ev_user_key))
            keys.append("charger")

        results = await asyncio.gather(*coros, return_exceptions=True)
        for key, result in zip(keys, results):
            data[key] = result if not isinstance(result, Exception) else None

        return data
