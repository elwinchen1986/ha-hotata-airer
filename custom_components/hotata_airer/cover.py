"""Cover platform for Hotata Airer with auto-stop at configured position."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .hub import HotataAccount, HotataHub

_LOGGER = logging.getLogger(__name__)


# HA 2026+: SET_POSITION (值=4)，旧版: SET_COVER_POSITION (值=8)
# 两者的值不同，所以必须用 hasattr 判断，不能直接 fallback 数值
if hasattr(CoverEntityFeature, "SET_POSITION"):
    _SET_COVER_POSITION = CoverEntityFeature.SET_POSITION
elif hasattr(CoverEntityFeature, "SET_COVER_POSITION"):
    _SET_COVER_POSITION = CoverEntityFeature.SET_COVER_POSITION
else:
    _SET_COVER_POSITION = CoverEntityFeature(8)  # 极旧版本兼容


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform."""
    account: HotataAccount = hass.data["hotata_airer"][entry.entry_id]
    async_add_entities(
        [HotataCover(hub) for hub in account.device_hubs.values()]
    )


class HotataCover(CoverEntity):
    """Representation of the Hotata airer cover.

    按下降键 → 运行 descent_time 秒 → 自动停止在最佳位置。
    上升键 → 一直升到顶。
    中途按停止 → 停在当前位置。
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | _SET_COVER_POSITION
    )
    _attr_has_entity_name = True
    _attr_translation_key = "cover"

    def __init__(self, hub: HotataHub) -> None:
        """Initialize the cover."""
        self._hub = hub
        self._attr_unique_id = f"{hub.iot_id}_cover"
        self._attr_device_info = hub.device_info
        self._position: int | None = 100
        self._closing_start: float | None = None
        self._stop_timer: Callable | None = None
        self._target_position: int | None = None  # 自动停止时的目标位置

    @property
    def _descent_time(self) -> int:
        """Return the configured descent time from hub."""
        return self._hub.descent_time

    @property
    def _use_time_simulation(self) -> bool:
        """Return True if time-based simulation is enabled."""
        return self._descent_time > 0

    async def _cancel_stop_timer(self) -> None:
        """Cancel pending auto-stop timer."""
        self._target_position = None
        if self._stop_timer is not None:
            self._stop_timer()
            self._stop_timer = None

    async def _async_auto_stop_cover(self, _now: Any) -> None:
        """Auto-stop callback: stops the motor after configured time."""
        self._stop_timer = None
        if await self._hub.control_cover("stop"):
            self._position = (
                self._target_position if self._target_position is not None else 0
            )
            self._closing_start = None
            self._target_position = None
            self._hub.state.simulated_position = self._position
            self.async_write_ha_state()
            _LOGGER.debug("Cover auto-stopped at position %d", self._position)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self._position = self._hub.state.simulated_position
        self.async_write_ha_state()
        self._hub.add_listener(self._handle_update)

    async def _handle_update(self) -> None:
        """Handle state update from hub."""
        hub_pos = self._hub.state.simulated_position
        if self._closing_start is not None:
            elapsed = time.time() - self._closing_start
            ratio = min(elapsed / self._descent_time, 1.0)
            estimated = max(0, 100 - int(ratio * 100))
            if estimated != self._position:
                self._position = estimated
                self._hub.state.simulated_position = estimated
                self.async_write_ha_state()
        elif hub_pos != self._position:
            self._position = hub_pos
            self.async_write_ha_state()

    @property
    def assumed_state(self) -> bool:
        """API 没有真实位置传感器时标记为假设状态。"""
        return self._hub.state.position is None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position."""
        return self._position

    @property
    def is_closed(self) -> bool:
        """Return True if the cover is at the lowest position."""
        return self._position is not None and self._position == 0

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return not self._hub.token_expired

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (上升/收起)."""
        await self._cancel_stop_timer()
        if await self._hub.control_cover("up"):
            if self._use_time_simulation:
                self._position = 100
                self._hub.state.simulated_position = 100
                self._closing_start = None
            await self._hub.async_update()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (下降/展开).

        基于当前位置计算剩余下降时间，确保不会超过设定的最低位置。
        """
        await self._cancel_stop_timer()
        if await self._hub.control_cover("down"):
            if self._use_time_simulation:
                self._target_position = 0
                self._closing_start = time.time()
                current = self._position or 100
                time_needed = max(1, current / 100 * self._descent_time)
                self._stop_timer = async_call_later(
                    self.hass, time_needed, self._async_auto_stop_cover
                )
                _LOGGER.debug(
                    "Cover descending from %d%%, auto-stop in %.1f seconds",
                    current,
                    time_needed,
                )
            await self._hub.async_update()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover (中途停止)."""
        await self._cancel_stop_timer()
        if await self._hub.control_cover("stop"):
            if self._use_time_simulation and self._closing_start is not None:
                elapsed = time.time() - self._closing_start
                ratio = min(elapsed / self._descent_time, 1.0)
                self._position = max(0, 100 - int(ratio * 100))
                self._hub.state.simulated_position = self._position
                self.async_write_ha_state()
                _LOGGER.debug(
                    "Cover stopped manually after %.1fs, position=%d",
                    elapsed,
                    self._position,
                )
            self._closing_start = None
            await self._hub.async_update()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover to a specific position."""
        target = kwargs.get("position", 100)
        current = self._position or 100

        if target == current:
            return

        await self._cancel_stop_timer()

        if target > current:
            # 上升
            if await self._hub.control_cover("up"):
                if self._use_time_simulation:
                    self._position = 100
                    self._hub.state.simulated_position = 100
                    self._closing_start = None
                await self._hub.async_update()
        else:
            # 下降到指定位置，按比例自动停止
            if await self._hub.control_cover("down"):
                if self._use_time_simulation:
                    self._target_position = target
                    self._closing_start = time.time()
                    # 需要运行的时间 = (当前位置 - 目标位置) / 100 * descent_time
                    time_needed = (current - target) / 100 * self._descent_time
                    self._stop_timer = async_call_later(
                        self.hass, time_needed, self._async_auto_stop_cover
                    )
                    _LOGGER.debug(
                        "Cover descending to %d%%, auto-stop in %.1f seconds",
                        target,
                        time_needed,
                    )
                await self._hub.async_update()