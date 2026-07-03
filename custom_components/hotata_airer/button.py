"""Button platform for Hotata Airer - manual position reset."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hub import HotataHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    hub: HotataHub = hass.data["hotata_airer"][entry.entry_id]
    async_add_entities([ResetPositionButton(hub)])


class ResetPositionButton(ButtonEntity):
    """Button to reset simulated position to 100 (fully up)."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_position"
    _attr_icon = "mdi:restore"

    def __init__(self, hub: HotataHub) -> None:
        """Initialize the button."""
        self._hub = hub
        self._attr_unique_id = f"{hub.iot_id}_reset_position"
        self._attr_device_info = hub.device_info

    async def async_press(self) -> None:
        """Handle the button press."""
        self._hub.state.simulated_position = 100
        _LOGGER.info("Simulated position reset to 100 (fully up)")
        await self._hub.notify_listeners()
