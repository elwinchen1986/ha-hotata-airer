"""Diagnostics support for Hotata Airer."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .hub import HotataHub

DOMAIN = "hotata_airer"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: HotataHub = hass.data[DOMAIN][entry.entry_id]

    data = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": {
                k: _truncate_token(v) if "token" in k.lower() else v
                for k, v in entry.data.items()
            },
            "options": entry.options,
        },
        "device_state": {
            "online": hub.state.online,
            "power_on": hub.state.power_on,
            "light_on": hub.state.light_on,
            "light_brightness": hub.state.light_brightness,
            "drying_on": hub.state.drying_on,
            "air_drying_on": hub.state.air_drying_on,
            "disinfection_on": hub.state.disinfection_on,
            "ions_on": hub.state.ions_on,
            "position": hub.state.position,
            "motor_control_mode": hub.state.motor_control_mode,
            "light_remaining_time": hub.state.light_remaining_time,
            "drying_remaining_time": hub.state.drying_remaining_time,
            "air_drying_remaining_time": hub.state.air_drying_remaining_time,
            "ions_remaining_time": hub.state.ions_remaining_time,
            "disinfection_remaining_time": hub.state.disinfection_remaining_time,
        },
        "runtime": {
            "descent_time": hub.descent_time,
            "token_expired": hub.token_expired,
            "token_permanently_invalid": hub.token_permanently_invalid,
            "last_error": hub.last_error,
            "user_id": hub.user_id,
            "iot_id": hub.iot_id,
        },
    }

    # Optionally include registered entities
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    data["entities"] = [
        {
            "entity_id": e.entity_id,
            "unique_id": e.unique_id,
            "platform": e.platform,
            "disabled_by": str(e.disabled_by),
            "hidden_by": str(e.hidden_by),
        }
        for e in entities
    ]

    # Optionally include device info
    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    data["devices"] = [
        {
            "id": d.id,
            "name": d.name,
            "model": d.model,
            "manufacturer": d.manufacturer,
            "sw_version": d.sw_version,
        }
        for d in devices
    ]

    return data


def _truncate_token(value: str, max_len: int = 40) -> str:
    """Truncate a token value for safe diagnostic display."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "..."
    return value