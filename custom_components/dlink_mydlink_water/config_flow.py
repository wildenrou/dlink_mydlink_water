from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MydlinkApiClient, MydlinkApiError
from .const import (
    CONF_ANDROID_ID,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_SCAN_INTERVAL,
    DEFAULT_ANDROID_ID,
    DEFAULT_DEVICE_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    session = async_get_clientsession(hass)
    client = MydlinkApiClient(
        session=session,
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        android_id=data.get(CONF_ANDROID_ID, DEFAULT_ANDROID_ID),
        device_name=data.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
    )
    await client.async_login()
    devices = await client.async_get_all_device_info()
    return {"devices_found": len(devices.get("devices", []))}


class DlinkMydlinkWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = max(
                int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)), MIN_SCAN_INTERVAL
            )
            try:
                info = await _validate_input(self.hass, user_input)
            except MydlinkApiError:
                _LOGGER.exception("mydlink validation failed")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during mydlink validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                title = f"mydlink Water ({info['devices_found']} device{'s' if info['devices_found'] != 1 else ''})"
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_ANDROID_ID, default=DEFAULT_ANDROID_ID): str,
                vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_DEVICE_NAME): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
