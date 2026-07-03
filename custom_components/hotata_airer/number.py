"""Number platform for Hotata Airer - configurable descent time."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hub import HotataHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    hub: HotataHub = hass.data["hotata_airer"][entry.entry_id]
    async_add_entities([DescentTimeNumber(hub)])


class DescentTimeNumber(NumberEntity):
    """Number entity for configuring the cover's full descent duration."""

    _attr_has_entity_name = True
    _attr_translation_key = "descent_time"
    _attr_native_min_value = 0
    _attr_native_max_value = 20
    _attr_native_step = 1
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, hub: HotataHub) -> None:
        """Initialize the number entity."""
        self._hub = hub
        self._attr_unique_id = f"{hub.iot_id}_descent_time"
        self._attr_device_info = hub.device_info

    @property
    def native_value(self) -> float:
        """Return the current descent time."""
        return float(self._hub.descent_time)

    @property
    def available(self) -> bool:
        """Config parameter is always available."""
        return True

    async def async_set_native_value(self, value: float) -> None:
        """Update descent time at runtime without reloading."""
        new_value = int(value)
        _LOGGER.info("Setting descent time to %d seconds", new_value)
        await self._hub.async_set_descent_time(new_value)
        self.async_write_ha_state()