"""Config flow for Hotata Airer integration (username/password login).

One config entry per Hotata account. The username and password are entered
once and stored in entry.data. Every physical airer under that account is
a record in entry.data["devices"].
"""

from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client

from .const import (
    API_DEVICE_LIST,
    API_LOGIN_PASSWORD,
    APP_KEY,
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
from .util import build_login_body, encrypt_password, generate_sign

_LOGGER = logging.getLogger(__name__)


def _classify_login_error(code: str, message: str) -> tuple[str, str]:
    """Map a server login error to a (error_key, user_facing_message) tuple.

    error_key matches a key in the translations ``config.error`` section so
    the config flow can render a localized message. The returned message is
    the raw server text, surfaced to the user via description_placeholders
    when no specific key fits.

    Known Hotata API login error codes (discovered via live API testing):
      1032 — 该手机号尚未注册 (phone number not registered)
      1035 — 密码加密错误 (password encryption error / empty password)
      1073 — login expired (refresh-token path)
    """
    msg = (message or "").strip()
    code = (code or "").strip()

    # 1032 = phone number not registered — the most common failure for users
    # who don't realize the username must be the exact phone number registered
    # in the Hotata app. Previously this was shown as "密码错误", misleading
    # users into resetting their password when the real issue was the phone #.
    if code == "1032":
        return "phone_not_registered", msg or "该手机号尚未注册"

    # 1035 = password encryption error — usually an empty or malformed password
    if code == "1035":
        return "invalid_auth", msg or "密码格式错误"

    # 1073 = login expired (refresh-token path); shouldn't normally happen
    # on a fresh password login, but handle it defensively.
    if code == "1073":
        return "auth_expired", msg or "登录已过期，请重新登录"

    # Common risk-control / captcha signals returned by the Hotata API.
    # The server message is the most reliable signal — codes are not documented.
    msg_lower = msg.lower()
    if any(k in msg for k in ("验证码", "图形验证", "滑块")) or "captcha" in msg_lower:
        return "captcha_required", msg or "登录过于频繁，需要验证码，请稍后通过 App 登录后重试"
    if any(k in msg for k in ("锁定", "冻结", "被封")) or "lock" in msg_lower:
        return "account_locked", msg or "账号已被锁定，请联系客服或稍后重试"
    if any(k in msg for k in ("频繁", "稍后", "稍后再试")) or "rate" in msg_lower:
        return "rate_limited", msg or "操作过于频繁，请稍后再试"
    if any(k in msg for k in ("密码错误", "密码不正确", "账号不存在", "用户不存在")):
        return "invalid_auth", msg or "用户名或密码错误"

    # Fallback: surface the raw server message so the user knows the real
    # reason instead of a generic "invalid auth".
    return "server_error", msg or f"服务器返回错误码 {code}"


async def _auth_with_password(
    hass: HomeAssistant,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Login with username/password and return account credentials.

    On success returns a dict with CONF_ACCESS_TOKEN / CONF_REFRESH_TOKEN /
    CONF_USER_ID.

    On failure returns ``{"error": <error_key>, "message": <server_msg>}``
    where ``error_key`` maps to a translation and ``message`` is the raw
    server text for display via description_placeholders.
    """
    import uuid

    async with httpx_client.get_async_client(hass) as client:
        body = build_login_body({
            "username": username.strip(),
            "registeredId": str(uuid.uuid4()),
            "password": encrypt_password(password),
        })
        try:
            resp = await client.post(
                API_LOGIN_PASSWORD,
                json=body,
                headers={"content-type": "application/json"},
                timeout=15,
            )
            data = resp.json()
        except Exception as e:
            _LOGGER.error("Login request error: %s", e)
            return {"error": "network_error", "message": str(e)}

        code = str(data.get("code", ""))
        message = data.get("message", "")

        if code != "000":
            error_key, server_msg = _classify_login_error(code, message)
            _LOGGER.error(
                "Login failed: code=%s, msg=%s → mapped to %s",
                code, message, error_key,
            )
            return {"error": error_key, "message": server_msg}

        d = data.get("data", {})
        user_id = d.get("userId") or d.get("userid")
        if not user_id:
            _LOGGER.error("No userId in login response: %s", d)
            return {"error": "server_error", "message": "登录响应缺少 userId"}

        token_type = d.get("tokenType", "bearer").strip()
        access_token = f"{token_type} {d.get('accessToken')}"
        refresh_token = d.get("refreshToken") or ""

        return {
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: refresh_token,
            CONF_USER_ID: user_id,
        }


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
    """Merge freshly-fetched devices into the existing record list."""
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
    """Handle the Hotata Airer config flow."""

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: authenticate with username/password."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] | None = None

        if user_input is not None:
            creds = await _auth_with_password(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if "error" in creds:
                errors["base"] = creds["error"]
                # Surface the raw server message for non-standard errors so
                # the user knows the real reason instead of a generic label.
                if creds["error"] in ("server_error", "network_error"):
                    placeholders = {"server_message": creds.get("message", "")}
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
                        title=f"Hotata ({user_input[CONF_USERNAME]})",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCESS_TOKEN: creds[CONF_ACCESS_TOKEN],
                            CONF_REFRESH_TOKEN: creds[CONF_REFRESH_TOKEN],
                            CONF_USER_ID: creds[CONF_USER_ID],
                            "devices": device_records,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_DESCENT_TIME, default=DEFAULT_DESCENT_TIME
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=20)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure: update credentials and/or refresh device list.

        Always show the username/password form first so the user can
        update their credentials explicitly. Silent device refresh
        happens automatically in the coordinator at runtime.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        placeholders: dict[str, str] | None = None

        if user_input is not None:
            creds = await _auth_with_password(
                self.hass, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if "error" in creds:
                errors["base"] = creds["error"]
                if creds["error"] in ("server_error", "network_error"):
                    placeholders = {"server_message": creds.get("message", "")}
            else:
                fetched = await _get_device_list(
                    self.hass, creds[CONF_ACCESS_TOKEN], creds[CONF_USER_ID]
                )
                merged = _merge_devices(entry.data.get("devices", []), fetched)
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCESS_TOKEN: creds[CONF_ACCESS_TOKEN],
                        CONF_REFRESH_TOKEN: creds[CONF_REFRESH_TOKEN],
                        CONF_USER_ID: creds[CONF_USER_ID],
                        "devices": merged,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=entry.data.get(CONF_USERNAME, ""),
                ): str,
                # Password is intentionally blank by default — even if we
                # have one stored, we ask the user to re-confirm so they
                # can change it if needed.
                vol.Required(CONF_PASSWORD, default=""): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )
