"""
Elevation service — uses Open-Meteo elevation API.
Results are cached to terrain_cache.json so the app works offline after first run.
Falls back to a flat 5 m if all else fails.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

_CACHE_PATH = Path(settings.terrain_cache_file)
_LOCK = asyncio.Lock()

_BATCH_SIZE = 100   # Open-Meteo elevation API max per request


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        with open(_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w") as f:
        json.dump(cache, f)


async def get_elevations(
    lats: list[float], lons: list[float]
) -> tuple[list[float], bool]:
    """
    Returns (elevations_list, from_cache).
    from_cache=True means at least some values came from file cache, not live API.
    """
    cache = _load_cache()
    results: dict[int, float] = {}
    missing_idx: list[int] = []

    for i, (la, lo) in enumerate(zip(lats, lons)):
        key = f"{la:.4f}_{lo:.4f}"
        if key in cache:
            results[i] = cache[key]
        else:
            missing_idx.append(i)

    from_cache = len(missing_idx) < len(lats) and len(missing_idx) > 0
    all_from_cache = len(missing_idx) == 0

    if missing_idx:
        # Batch fetch from Open-Meteo Elevation API
        for batch_start in range(0, len(missing_idx), _BATCH_SIZE):
            batch = missing_idx[batch_start: batch_start + _BATCH_SIZE]
            b_lats = [lats[i] for i in batch]
            b_lons = [lons[i] for i in batch]
            fetched = await _fetch_elevation_batch(b_lats, b_lons)
            for idx, elev in zip(batch, fetched):
                results[idx] = elev
                key = f"{lats[idx]:.4f}_{lons[idx]:.4f}"
                cache[key] = elev

        async with _LOCK:
            _save_cache(cache)

    elevations = [results.get(i, 5.0) for i in range(len(lats))]
    return elevations, (from_cache or all_from_cache)


async def _fetch_elevation_batch(lats: list[float], lons: list[float]) -> list[float]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/elevation",
                params={
                    "latitude": ",".join(f"{v:.5f}" for v in lats),
                    "longitude": ",".join(f"{v:.5f}" for v in lons),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [float(e) for e in data.get("elevation", [5.0] * len(lats))]
    except Exception:
        return [5.0] * len(lats)
