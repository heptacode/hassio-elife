from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DEVICE_UUID): str,
    }
)

STEP_DEVICES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AC_UIDS): str,
        vol.Required(CONF_LIGHT_UIDS): str,
        vol.Required(CONF_HEAT_UIDS): str,
        vol.Required(CONF_VENT_UID): str,
        vol.Required(CONF_ELEVATOR_UID): str,
        vol.Optional(CONF_EV_ROOM_KEY, default=""): str,
        vol.Optional(CONF_EV_USER_KEY, default=""): str,
    }
)

_JSON_ARRAY_FIELDS = (CONF_AC_UIDS, CONF_LIGHT_UIDS, CONF_HEAT_UIDS)


def _validate_json_arrays(user_input: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in _JSON_ARRAY_FIELDS:
        try:
            parsed = json.loads(user_input[key])
            if not isinstance(parsed, list):
                raise ValueError("not a list")
        except (json.JSONDecodeError, ValueError):
            errors[key] = "invalid_json_array"
    return errors


class ELifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._user_input: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Step 1: credentials
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = ELifeAPIClient(
                    hass=self.hass,
                    session=async_get_clientsession(self.hass),
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    device_uuid=user_input[CONF_DEVICE_UUID],
                )
                await client._refresh_token()
            except ELifeAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._user_input = user_input
                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: device UIDs
    # ------------------------------------------------------------------

    async def async_step_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_json_arrays(user_input)
            if not errors:
                await self.async_set_unique_id(self._user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"e-Life",
                    data={**self._user_input, **user_input},
                )

        return self.async_show_form(
            step_id="devices",
            data_schema=STEP_DEVICES_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Reauth flow (triggered by ConfigEntryAuthFailed)
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = ELifeAPIClient(
                    hass=self.hass,
                    session=async_get_clientsession(self.hass),
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    device_uuid=user_input[CONF_DEVICE_UUID],
                )
                await client._refresh_token()
            except ELifeAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry is not None:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, **user_input},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
