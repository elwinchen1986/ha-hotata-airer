"""Config flow for Hotata Airer integration (single account entry, device list).

Xiaomi-style model: one config entry is created per Hotata account. The refresh
token is entered exactly once and stored in ``entry.data``. Every physical
airer under that account is a record in ``entry.data["devices"]`` — there are
**no config subentries**. Adding another device later (or renewing an expired
token) is handled by the reconfigure flow, which re-fetches the account's
device list and merges in any new device; the token is never asked for again
unless it has actually expired.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client

from .const import (
    API_DEVICE_LIST,
    API_REFRESH_TOKEN,
    APP_KEY,
    APP_SECRET,
    APP_VERSION,
    CONF_ACCESS_TOKEN,
    CONF_DESCENT_TIME,
    CONF_IOT_ID,
    CONF_NAME,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DEFAULT_DESCENT_TIME,
    DEFAULT_NAME,
    DOMAIN,
    IMEI,
    PHONE_MODEL,
    SYS_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def generate_sign(payload: dict[str, Any]) -> str:
    """Generate MD5 signature for API request."""
    p = payload.copy()
    p.pop("sign", None)
    arr = []
    for k in sorted(p.keys()):
        v = p[k]
        if v is None or v == "":
            continue
        if isinstance(v, (dict, list)):
            continue
        arr.append(f"{k}={v}")
    raw = "&".join(arr) + APP_SECRET
    return hashlib.md5(raw.encode("utf8")).hexdigest()


async def _auth_with_refresh_token(
    hass: HomeAssistant,
    refresh_token: str,
) -> dict[str, Any] | None:
    """Exchange a refresh token for account credentials.

    Returns a dict with CONF_ACCESS_TOKEN / CONF_REFRESH_TOKEN / CONF_USER_ID,
    or None if authentication failed.
    """
    async with httpx_client.get_async_client(hass) as client:
        ts = int(time.time() * 1000)
        refresh_payload = {
            "refreshToken": refresh_token,
            "appKey": APP_KEY,
            "appVersion": APP_VERSION,
            "timestamp": ts,
            "traceId": f"ha_refresh_{ts}",
            "sysVersion": SYS_VERSION,
            "phoneModel": PHONE_MODEL,
            "imei": IMEI,
        }
        refresh_payload["sign"] = generate_sign(refresh_payload)

        headers = {
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            resp = await client.post(
                API_REFRESH_TOKEN,
                json=refresh_payload,
                headers=headers,
                timeout=10,
            )
            try:
                data = resp.json()
            except Exception as json_err:
                _LOGGER.error(
                    "Failed to parse JSON response: %s. Response: %s",
                    json_err,
                    resp.text[:500],
                )
                return None

            if data.get("code") != "000":
                _LOGGER.error("Refresh token failed with code: %s", data.get("code"))
                return None

            d = data.get("data", {})
            user_id = d.get("userId") or d.get("userid")
            if not user_id:
                _LOGGER.error("No userId in refresh response: %s", d)
                return None

            token_type = d.get("tokenType", "bearer").strip()
            access_token = f"{token_type} {d.get('accessToken')}"
            new_refresh_token = d.get("refreshToken") or refresh_token

            return {
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: new_refresh_token,
                CONF_USER_ID: user_id,
            }
        except Exception as e:
            _LOGGER.exception("Refresh token request error: %s", e)
            return None


async def _get_device_list(
    hass: HomeAssistant,
    access_token: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """Fetch the device list for an account."""
    ts = int(time.time() * 1000)
    payload = {
        "userid": user_id,
        "userId": user_id,
        "appKey": APP_KEY,
        "appVersion": APP_VERSION,
        "timestamp": ts,
        "traceId": f"ha_list_{ts}",
        "sysVersion": SYS_VERSION,
        "phoneModel": PHONE_MODEL,
        "imei": IMEI,
    }
    payload["sign"] = generate_sign(payload)

    async with httpx_client.get_async_client(hass) as client:
        try:
            resp = await client.post(
                API_DEVICE_LIST,
                json=payload,
                headers={
                    "content-type": "application/json",
                    "authorization": access_token,
                },
                timeout=10,
            )
            data = resp.json()
            return data.get("data", []) if data.get("code") == "000" else []
        except Exception as e:
            _LOGGER.error("Device list error: %s", e)
            return []


def _device_metadata(device: dict[str, Any], descent_time: int) -> dict[str, Any]:
    """Extract persistent device metadata used by the device hub / registry."""
    iot_id = device.get("iotid") or device.get("iotId")
    name = (
        device.get("deviceNickName")
        or device.get("devicenickname")
        or device.get("deviceName")
        or DEFAULT_NAME
    )
    return {
        CONF_IOT_ID: iot_id,
        CONF_NAME: name,
        "mac": device.get("devicename", ""),
        "productname": device.get("productname", ""),
        "devicetype": device.get("devicetype", 0),
        "devicenickname": device.get("devicenickname", ""),
        "productkey": device.get("productkey", ""),
        CONF_DESCENT_TIME: descent_time,
    }


def _merge_devices(
    existing: list[dict[str, Any]], fetched: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge freshly-fetched devices into the existing record list.

    Existing records (keyed by iotId) are preserved so any per-device config
    such as ``descent_time`` survives a reconfigure.
    """
    by_iot: dict[str, dict[str, Any]] = {
        d[CONF_IOT_ID]: d for d in existing if d.get(CONF_IOT_ID)
    }
    for dev in fetched:
        iot_id = dev.get("iotid") or dev.get("iotId")
        if not iot_id or iot_id in by_iot:
            continue
        by_iot[iot_id] = dev
    return list(by_iot.values())


class HotataAirerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Hotata Airer config flow.

    One account entry is created per Hotata account (the refresh token is
    entered exactly once). Each physical airer becomes a device record inside
    the account entry's data — adding another device later never asks for the
    token again.
    """

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: authenticate the account (refresh token entered ONCE)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            creds = await _auth_with_refresh_token(
                self.hass, user_input[CONF_REFRESH_TOKEN]
            )
            if creds is None:
                errors["base"] = "invalid_auth"
            else:
                devices = await _get_device_list(
                    self.hass, creds[CONF_ACCESS_TOKEN], creds[CONF_USER_ID]
                )
                descent_time = int(
                    user_input.get(CONF_DESCENT_TIME, DEFAULT_DESCENT_TIME)
                )
                device_records = [
                    _device_metadata(d, descent_time)
                    for d in devices
                    if (d.get("iotid") or d.get("iotId"))
                ]
                if not device_records:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(creds[CONF_USER_ID])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Hotata 账号 ({creds[CONF_USER_ID]})",
                        data={
                            CONF_ACCESS_TOKEN: creds[CONF_ACCESS_TOKEN],
                            CONF_REFRESH_TOKEN: creds[CONF_REFRESH_TOKEN],
                            CONF_USER_ID: creds[CONF_USER_ID],
                            "devices": device_records,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_REFRESH_TOKEN): str,
                vol.Required(
                    CONF_DESCENT_TIME, default=DEFAULT_DESCENT_TIME
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=20)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure: renew an expired token and/or pull in new devices.

        If the stored token is still valid we silently re-fetch the account's
        device list and merge in any new device, then reload — no prompt. Only
        when the token has actually expired do we ask the user to paste a new
        refresh token.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            creds = await _auth_with_refresh_token(
                self.hass, user_input[CONF_REFRESH_TOKEN]
            )
            if creds is None:
                errors["base"] = "invalid_token"
            else:
                fetched = await _get_device_list(
                    self.hass, creds[CONF_ACCESS_TOKEN], creds[CONF_USER_ID]
                )
                merged = _merge_devices(entry.data.get("devices", []), fetched)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: creds[CONF_ACCESS_TOKEN],
                        CONF_REFRESH_TOKEN: creds[CONF_REFRESH_TOKEN],
                        "devices": merged,
                    },
                )

        # Silent path: try the existing token first; merge any new device.
        existing = entry.data.get("devices", [])
        silent = await _get_device_list(
            self.hass, entry.data[CONF_ACCESS_TOKEN], entry.data[CONF_USER_ID]
        )
        if silent:
            merged = _merge_devices(existing, silent)
            if merged != existing:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={"devices": merged},
                )
            # Token still valid and no new device — nothing to do.
            return self.async_abort(reason="no_changes")

        # Token expired (or list fetch failed): ask for a fresh refresh token.
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REFRESH_TOKEN,
                    default=entry.data.get(CONF_REFRESH_TOKEN, ""),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )
