"""ELife Smart API client.

Replicates the logic from:
  - src/app/utils/api.ts   (ky client, CSRF, token refresh, endpoint map)
  - src/app/utils/kv.ts    (token storage → HA Store)
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    CSRF_USER_AGENT,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class ELifeAuthError(Exception):
    """Raised when authentication fails even after a token refresh attempt."""


class ELifeAPIError(Exception):
    """Raised for non-auth API errors."""


class ELifeAPIClient:
    """Authenticated HTTP client for smartelife.apt.co.kr."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        username: str,
        password: str,
        device_uuid: str,
    ) -> None:
        self._hass = hass
        self._session = session
        self._username = username
        self._password = password
        self._device_uuid = device_uuid
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._token: str | None = None
        self._token_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Load persisted token from HA storage. Does not validate it."""
        data = await self._store.async_load()
        if data:
            self._token = data.get("token")
            _LOGGER.debug("Loaded persisted token from storage")

    # ------------------------------------------------------------------
    # Auth internals
    # ------------------------------------------------------------------

    async def _get_csrf(self) -> str:
        """Fetch a one-time CSRF token. Must be called before every request."""
        async with self._session.post(
            f"{BASE_URL}/common/nativeToken.ajax",
            headers={"User-Agent": CSRF_USER_AGENT},
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
            return payload["value"]

    async def _do_login(self, csrf: str) -> str:
        """Perform credential login and return the new daelim_elife token."""
        async with self._session.post(
            f"{BASE_URL}/login.ajax",
            headers={
                "User-Agent": USER_AGENT,
                "Origin": BASE_URL,
                "_csrf": csrf,
            },
            json={
                "input_dv_make_info": "Apple",
                "input_dv_model_info": "iPhone17,2",
                "input_dv_osver_info": "26.1",
                "input_password": self._password,
                "input_memb_uid": "",
                "input_dv_uuid": self._device_uuid,
                "input_version": "1.1.4",
                "input_acc_os_info": "ios",
                "input_push_token": "",
                "input_flag": "login",
                "input_username": self._username,
                "input_hm_cd": "",
                "input_auto_login": "on",
            },
        ) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
            token = payload.get("daelim_elife")
            if not token:
                raise ELifeAuthError("Login response missing daelim_elife token")
            return token

    async def _refresh_token(self) -> str:
        """Thread-safe token refresh. Only one refresh runs at a time.

        If another coroutine refreshed the token while we waited for the lock,
        we return the already-refreshed token without re-logging in.
        """
        async with self._token_lock:
            if self._token is not None:
                return self._token
            _LOGGER.debug("Refreshing token via login")
            csrf = await self._get_csrf()
            token = await self._do_login(csrf)
            self._token = token
            await self._store.async_save({"token": token})
            return token

    # ------------------------------------------------------------------
    # Core request (mirrors ky hooks: beforeRequest / afterResponse / beforeRetry)
    # ------------------------------------------------------------------

    async def _request(self, path: str, payload: dict) -> dict:
        """POST to BASE_URL/path with auth headers. Retries once on auth error."""
        if self._token is None:
            self._token = await self._refresh_token()

        for attempt in range(2):
            # CSRF is a one-time token — must be fetched fresh on every attempt
            csrf = await self._get_csrf()
            headers = {
                "User-Agent": USER_AGENT,
                "Origin": BASE_URL,
                "_csrf": csrf,
                "daelim_elife": self._token or "",
            }
            async with self._session.post(
                f"{BASE_URL}/{path}",
                headers=headers,
                json=payload,
            ) as resp:
                raw = await resp.text()

                # Auth error: HTTP 401 or sentinel text responses
                if resp.status == 401 or raw in ("accountError2", "requireLoginForAjax"):
                    if attempt == 0:
                        _LOGGER.debug("Auth error (%s), refreshing token", raw.strip() or resp.status)
                        self._token = None
                        self._token = await self._refresh_token()
                        continue
                    raise ELifeAuthError(
                        f"Authentication failed after retry: {raw.strip()}"
                    )

                resp.raise_for_status()

                try:
                    return json.loads(raw)
                except json.JSONDecodeError as err:
                    raise ELifeAPIError(
                        f"Invalid JSON from {path}: {raw[:200]}"
                    ) from err

        raise ELifeAPIError("Request loop exited unexpectedly")

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    async def get_ac_status(self, uid: str) -> dict:
        return await self._request(
            "controls/device/status.ajax",
            {"type": "aircon", "uid": uid},
        )

    async def get_light_status(self, uid: str) -> dict:
        return await self._request(
            "controls/device/status.ajax",
            {"type": "light", "uid": uid},
        )

    async def get_vent_status(self, uid: str) -> dict:
        return await self._request(
            "controls/device/status.ajax",
            {"type": "vent", "uid": uid},
        )

    async def get_heat_status(self, uid: str) -> dict:
        return await self._request(
            "controls/device/status.ajax",
            {"type": "heat", "uid": uid},
        )

    # ------------------------------------------------------------------
    # Control commands
    # ------------------------------------------------------------------

    async def control_ac(self, uid: str, control: str, set_temp: str) -> dict:
        return await self._request(
            "device/control.ajax",
            {
                "type": "aircon",
                "uid": uid,
                "operation": {"control": control, "set_temp": set_temp},
            },
        )

    async def control_light(self, uid: str, control: str) -> dict:
        return await self._request(
            "device/control.ajax",
            {
                "type": "light",
                "uid": uid,
                "operation": {"control": control},
            },
        )

    async def control_vent(self, uid: str, control: str, wind_speed: str = "high") -> dict:
        operation: dict = {"control": control}
        if control == "on":
            operation["off_rsv_time"] = "0"
            operation["wind_speed"] = wind_speed
        return await self._request(
            "device/control.ajax",
            {"type": "vent", "uid": uid, "operation": operation},
        )

    async def call_elevator(self, uid: str) -> dict:
        return await self._request(
            "common/data.ajax",
            {
                "header": {"category": "elevator", "type": "call", "command": "control_request"},
                "data": {"uid": uid, "operation": {"control": "down"}},
            },
        )

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    async def get_outdoor_climate(self) -> dict:
        return await self._request(
            "main/weatherInfo.ajax",
            {"weather": "today", "air": "outdoor"},
        )

    async def get_energy(self) -> dict:
        now = dt_util.now()
        return await self._request(
            "common/data.ajax",
            {
                "header": {"category": "ems", "type": "current_use", "command": "query_request"},
                "data": {"year": str(now.year), "month": str(now.month)},
            },
        )

    async def get_visitor(self) -> dict:
        return await self._request(
            "common/data.ajax",
            {
                "header": {"category": "board", "type": "visitor", "command": "query_request"},
                "data": {"page": "1", "count": "5", "include_image": "Y"},
            },
        )

    async def get_charger(self, ev_room_key: str, ev_user_key: str) -> dict:
        return await self._request(
            "common/data.ajax",
            {
                "tabType": "charger",
                "header": {"category": "board", "type": "ev_list", "command": "query_request"},
                "data": {"roomkey": ev_room_key, "userkey": ev_user_key, "count": "999"},
            },
        )
