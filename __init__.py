from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

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
    SERVICE_CLEAR_TOKEN,
)
from .coordinator import ELifeCoordinator

PLATFORMS = [
    Platform.LIGHT,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.BUTTON,
    Platform.SENSOR,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_DEVICE_UUID): str,
                vol.Required(CONF_AC_UIDS): [str],
                vol.Required(CONF_LIGHT_UIDS): [str],
                vol.Required(CONF_HEAT_UIDS): [str],
                vol.Required(CONF_VENT_UID): str,
                vol.Required(CONF_ELEVATOR_UID): str,
                vol.Optional(CONF_EV_ROOM_KEY, default=""): str,
                vol.Optional(CONF_EV_USER_KEY, default=""): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def async_handle_clear_token(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id")
        coordinators: dict[str, ELifeCoordinator] = hass.data.get(DOMAIN, {})

        if target_entry_id:
            coordinator = coordinators.get(target_entry_id)
            if coordinator is None:
                return
            await coordinator.client.async_clear_token()
            await hass.config_entries.async_reload(target_entry_id)
            return

        for entry_id, coordinator in list(coordinators.items()):
            await coordinator.client.async_clear_token()
            await hass.config_entries.async_reload(entry_id)

    if not hass.services.has_service(DOMAIN, SERVICE_CLEAR_TOKEN):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_TOKEN,
            async_handle_clear_token,
            schema=vol.Schema({vol.Optional("entry_id"): str}),
        )

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = ELifeCoordinator(hass, entry)
    await coordinator.client.async_init()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
