"""Hotata Airer - Custom Home Assistant Integration.

Account model (Xiaomi-style): one config entry per Hotata account owns the
credentials, backed by a single :class:`HotataAccount`. Every physical airer
is a *device record stored inside the account entry's data* (``entry.data``
holds a ``devices`` list). There are **no config subentries** — all devices
share the one entry and the one token, exactly like the official xiaomi_home
integration does.

Backward compatibility: pre-2.4 single-device entries stored the device inline
(token + iot_id at the top level of ``entry.data``). They have no ``devices``
key, so :func:`async_setup_entry` detects that shape and treats the whole
``entry.data`` as a single-device record — no data migration and no user
action required. Multi-device 2.2 setups never worked and are out of scope;
those users simply re-add the account.

Platforms are wired once per account entry via
``async_forward_entry_setups``; each platform iterates
``account.device_hubs`` and creates one entity per device.
"""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_IOT_ID, DOMAIN
from .hub import HotataAccount, HotataHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "binary_sensor",
    "button",
    "cover",
    "light",
    "switch",
    "sensor",
    "number",
]


def _normalize_devices(entry: ConfigEntry) -> list[dict]:
    """Return the device records for an entry.

    New installs carry ``entry.data["devices"]`` (a list). Legacy pre-2.4
    single-device entries have the device fields at the top level of
    ``entry.data``; we treat the whole dict as a single device record.
    """
    devices = entry.data.get("devices")
    if devices:
        return list(devices)
    return [dict(entry.data)]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Hotata account config entry and all of its devices.

    The shared token owner and the preventive token-refresh timer live here.
    Each device gets its own :class:`HotataHub`, registered on the account so
    platforms can enumerate them.
    """
    # HA may invoke setup twice in a reload race; only wire once.
    if hass.data.get(DOMAIN, {}).get(entry.entry_id) is not None:
        return True

    account = HotataAccount(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = account

    for device in _normalize_devices(entry):
        iot_id = device.get(CONF_IOT_ID)
        if not iot_id:
            _LOGGER.warning("Skipping device record without iotId: %s", device)
            continue
        hub = HotataHub(hass, device, account)
        account.register_device(hub)
        await hub.async_load_persisted_config()
        await hub.start_polling()

    await account.start_scheduled_refresh()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Upgrade legacy entries to the current schema version.

    Pre-2.4 single-device entries stored the device inline (token + iot_id at
    the top level of ``entry.data``). The runtime handles that shape
    transparently in :func:`async_setup_entry` via :func:`_normalize_devices`,
    so no data transformation is needed — we only bump the version marker.
    There is deliberately no prompt and no forced re-install: single-device
    users upgrade seamlessly. Multi-device 2.2 setups never worked and are out
    of scope; affected users re-add the account.
    """
    if entry.version < 2:
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options / reconfigure updates by reloading the account entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the account entry and every device hub under it."""
    account: HotataAccount | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if account is None:
        return True
    account.stop_scheduled_refresh()
    for hub in account.device_hubs.values():
        hub.stop_polling()
    return all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
