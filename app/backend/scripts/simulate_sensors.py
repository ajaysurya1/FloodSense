#!/usr/bin/env python3
"""
D2 Sensor Simulator.
Runs 5 nodes (1 "real" CSV-backed + 4 simulated) posting every 10s.
Includes a scripted "sudden rise" scenario at t+90s for the override demo.
All simulated readings are tagged data_source=SIMULATED.

Usage:
    python -m scripts.simulate_sensors [--url http://localhost:8000]
"""
from __future__ import annotations

import argparse
import asyncio
import math
import time
from datetime import datetime, timezone

import httpx

# ── Node definitions ───────────────────────────────────────────────────────────
NODES = [
    {
        "device_id": "FS-001",
        "lat": 13.0132, "lon": 80.2448,
        "name": "Kotturpuram Main Road",
        "base_level": 12.0,
        "data_source": "SIMULATED",
    },
    {
        "device_id": "FS-002",
        "lat": 13.0075, "lon": 80.2510,
        "name": "Adyar Bridge Underpass",
        "base_level": 8.0,
        "data_source": "SIMULATED",
    },
    {
        "device_id": "FS-003",
        "lat": 13.0185, "lon": 80.2478,
        "name": "Gandhi Nagar",
        "base_level": 15.0,
        "data_source": "SIMULATED",
    },
    {
        "device_id": "FS-004",
        "lat": 13.0220, "lon": 80.2395,
        "name": "Srinivasa Nagar",
        "base_level": 20.0,
        "data_source": "SIMULATED",
    },
    {
        "device_id": "FS-005",
        "lat": 13.0098, "lon": 80.2472,
        "name": "MRTS Underpass (SUDDEN RISE demo)",
        "base_level": 10.0,
        "data_source": "SIMULATED",
    },
]

START_TIME = time.time()
SUDDEN_RISE_NODE = "FS-005"
SUDDEN_RISE_AT_S = 90   # trigger after 90 seconds


def _level(node: dict, elapsed: float) -> float:
    """Compute simulated water level."""
    base = node["base_level"]
    # Gentle rain rise over time
    rain_rise = elapsed * 0.04   # ~2.4 cm/min background
    # Sinusoidal variation
    variation = 2.0 * math.sin(elapsed / 120 * math.pi)

    # Sudden-rise scenario for FS-005
    if node["device_id"] == SUDDEN_RISE_NODE and elapsed >= SUDDEN_RISE_AT_S:
        surge = (elapsed - SUDDEN_RISE_AT_S) * 0.8  # 0.8 cm/s = 48 cm/min
        return round(min(base + rain_rise + surge, 120.0), 1)

    return round(max(0.0, base + rain_rise + variation), 1)


def _battery(elapsed: float) -> float:
    return round(max(20.0, 95.0 - elapsed * 0.01), 1)


async def post_reading(client: httpx.AsyncClient, base_url: str, node: dict, elapsed: float):
    level = _level(node, elapsed)
    payload = {
        "device_id": node["device_id"],
        "ts": datetime.now(timezone.utc).isoformat(),
        "water_level_cm": level,
        "rainfall_mm": None,
        "battery_pct": _battery(elapsed),
        "rssi": -65 - int(elapsed % 20),
        "lat": node["lat"],
        "lon": node["lon"],
        "data_source": node["data_source"],
    }
    try:
        resp = await client.post(f"{base_url}/api/sensors/readings", json=payload, timeout=5.0)
        status = resp.json()
        alert_str = " ⚠️ ALERT OVERRIDE!" if status.get("alert_active") else ""
        print(
            f"[{node['device_id']}] {node['name']:30s} | level={level:6.1f} cm | "
            f"ror={status.get('rate_of_rise_cm_per_5min', 0):.1f} cm/5min{alert_str}"
        )
    except Exception as e:
        print(f"[{node['device_id']}] POST failed: {e}")


async def main(base_url: str):
    print(f"[FloodSense] Sensor Simulator -- posting to {base_url}")
    print(f"   Sudden-rise scenario on {SUDDEN_RISE_NODE} triggers at t+{SUDDEN_RISE_AT_S}s")
    print(f"   All readings tagged SIMULATED\n")
    async with httpx.AsyncClient() as client:
        while True:
            elapsed = time.time() - START_TIME
            print(f"--- t={elapsed:.0f}s ---")
            tasks = [post_reading(client, base_url, node, elapsed) for node in NODES]
            await asyncio.gather(*tasks)
            await asyncio.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(main(args.url))
