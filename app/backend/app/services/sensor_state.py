"""
Sensor state cache — keeps the latest reading per device in memory
for fast access by the risk engine and other services.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

_STATE: dict[str, dict[str, Any]] = {}
_LOCK = asyncio.Lock()


async def update_sensor_state(device_id: str, state: dict) -> None:
    async with _LOCK:
        _STATE[device_id] = state


async def get_latest_sensor_state() -> dict[str, dict]:
    async with _LOCK:
        return dict(_STATE)


async def get_device_state(device_id: str) -> dict | None:
    async with _LOCK:
        return _STATE.get(device_id)
