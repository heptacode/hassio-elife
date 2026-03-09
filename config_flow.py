from __future__ import annotations

import json
import logging
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

_LOGGER = logging.getLogger(__name__)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DEVICE_UUID): str,
    }
)

_LIST_FIELDS = (CONF_AC_UIDS, CONF_LIGHT_UIDS, CONF_HEAT_UIDS)


class ELifeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """UI 설정은 지원하지 않음. configuration.yaml을 사용."""
        return self.async_abort(reason="yaml_only")

    # ------------------------------------------------------------------
    # YAML import flow
    # ------------------------------------------------------------------

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> FlowResult:
        await self.async_set_unique_id(import_data[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        data = dict(import_data)
        for key in _LIST_FIELDS:
            if isinstance(data[key], list):
                data[key] = json.dumps(data[key])

        try:
            client = ELifeAPIClient(
                hass=self.hass,
                session=async_get_clientsession(self.hass),
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
                device_uuid=data[CONF_DEVICE_UUID],
            )
            await client._refresh_token()
        except ELifeAuthError:
            _LOGGER.error("e-Life YAML import failed: invalid credentials")
            return self.async_abort(reason="invalid_auth")
        except Exception:
            _LOGGER.error("e-Life YAML import failed: cannot connect")
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="e-Life", data=data)

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
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )
