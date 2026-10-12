"""
Open-Meteo forecast service.
Fetches minutely_15 and hourly precipitation.
Caches responses for `forecast_cache_minutes` minutes.
Falls back to stale cache if the API fails.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.config import settings

_CACHE: dict[str, Any] = {}          # key → {data, ts}
_LOCK = asyncio.Lock()

_BASE = "https://api.open-meteo.com/v1/forecast"


async def get_forecast(lat: float, lon: float, horizon_min: int) -> dict:
    # Coarse grid (0.02 deg ~ 2 km, matching NWP model resolution)
    cache_key = f"{round(lat, 2):.2f}_{round(lon, 2):.2f}_{horizon_min}"
    now = time.time()

    async with _LOCK:
        entry = _CACHE.get(cache_key)
        if entry and (now - entry["ts"]) < settings.forecast_cache_minutes * 60:
            return entry["data"]

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(_BASE, params={
                "latitude": lat,
                "longitude": lon,
                "minutely_15": "precipitation",
                "hourly": "precipitation",
                "forecast_days": 1,
                "timezone": "Asia/Kolkata",
            })
            resp.raise_for_status()
            raw = resp.json()
    except Exception:
        # Return stale if available, else zeros
        if entry:
            stale = dict(entry["data"])
            stale["age_min"] = (now - entry["ts"]) / 60
            return stale
        return {"intensity_mm_3h": 0.0, "cumulative_mm": 0.0, "source": "LIVE-FAILED", "age_min": 999}

    data = _parse_forecast(raw, horizon_min)
    data["source"] = "LIVE"
    data["age_min"] = 0

    async with _LOCK:
        _CACHE[cache_key] = {"data": data, "ts": now}
    return data


def _parse_forecast(raw: dict, horizon_min: int) -> dict:
    """Extract intensity in next 3h and cumulative over horizon."""
    try:
        m15 = raw.get("minutely_15", {})
        times = m15.get("time", [])
        precip_15 = m15.get("precipitation", [])

        if not times:
            return {"intensity_mm_3h": 0.0, "cumulative_mm": 0.0}

        # Take next 12 intervals (3 hours of minutely_15)
        intensity = sum(precip_15[:12]) if len(precip_15) >= 12 else sum(precip_15)

        # Cumulative over horizon
        n_intervals = min(int(horizon_min / 15), len(precip_15))
        cumulative = sum(precip_15[:n_intervals])

        return {
            "intensity_mm_3h": round(float(intensity), 2),
            "cumulative_mm": round(float(cumulative), 2),
        }
    except Exception:
        return {"intensity_mm_3h": 0.0, "cumulative_mm": 0.0}
