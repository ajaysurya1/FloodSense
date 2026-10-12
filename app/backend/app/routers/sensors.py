"""D2 – IoT Sensors router."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_db
from app.services.sensor_state import update_sensor_state, get_latest_sensor_state

router = APIRouter()


class SensorReading(BaseModel):
    device_id: str
    ts: str
    water_level_cm: float
    rainfall_mm: float | None = None
    battery_pct: float | None = None
    rssi: int | None = None
    lat: float | None = None
    lon: float | None = None
    data_source: str = "SIMULATED"


@router.post("/sensors/readings")
async def post_reading(reading: SensorReading, db: aiosqlite.Connection = Depends(get_db)):
    """Ingest a sensor reading and update device state."""
    # Derive ward_id server-side from lat/lon; never trust the client to send it.
    ward_id = _derive_ward_id(reading.lat, reading.lon)

    await db.execute(
        """INSERT INTO sensor_readings
           (device_id, ts, water_level_cm, rainfall_mm, battery_pct, rssi, lat, lon, data_source, ward_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (reading.device_id, reading.ts, reading.water_level_cm,
         reading.rainfall_mm, reading.battery_pct, reading.rssi,
         reading.lat, reading.lon, reading.data_source, ward_id),
    )
    await db.commit()

    # Compute rate of rise from last N readings
    cursor = await db.execute(
        """SELECT water_level_cm, ts FROM sensor_readings
           WHERE device_id = ? ORDER BY ts DESC LIMIT ?""",
        (reading.device_id, settings.smoothing_readings),
    )
    rows = await cursor.fetchall()
    ror = _compute_ror(rows)

    # Determine device status
    now_iso = datetime.now(timezone.utc).isoformat()
    status = "online"

    alert_active = 0
    alert_reason = None
    if ror >= settings.ror_urgent_cm_per_5min:
        alert_active = 1
        alert_reason = f"Ground sensor override: rate of rise {ror:.1f} cm/5min >= threshold {settings.ror_urgent_cm_per_5min}"
    if reading.water_level_cm >= settings.critical_level_cm:
        alert_active = 1
        alert_reason = f"Ground sensor override: water level {reading.water_level_cm:.0f} cm >= critical {settings.critical_level_cm}"

    state = {
        "device_id": reading.device_id,
        "last_seen": reading.ts,
        "last_level": reading.water_level_cm,
        "rate_of_rise": ror,
        "battery_pct": reading.battery_pct,
        "rssi": reading.rssi,
        "lat": reading.lat,
        "lon": reading.lon,
        "status": status,
        "data_source": reading.data_source,
        "alert_active": alert_active,
        "alert_reason": alert_reason,
        "ward_id": ward_id,
    }

    await db.execute(
        """INSERT OR REPLACE INTO sensor_devices
           (device_id, last_seen, last_level, rate_of_rise, battery_pct, rssi, lat, lon, status, data_source, alert_active, ward_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (reading.device_id, reading.ts, reading.water_level_cm, ror,
         reading.battery_pct, reading.rssi, reading.lat, reading.lon,
         status, reading.data_source, alert_active, ward_id),
    )
    await db.commit()
    await update_sensor_state(reading.device_id, state)

    return {
        "accepted": True,
        "device_id": reading.device_id,
        "rate_of_rise_cm_per_5min": ror,
        "status": status,
        "alert_active": bool(alert_active),
        "alert_reason": alert_reason,
        "data_source": reading.data_source,
        "ward_id": ward_id,
    }


@router.get("/sensors")
async def get_sensors(
    ward_id: str | None = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return latest state of all sensor nodes, optionally filtered by ward."""
    if ward_id:
        cursor = await db.execute(
            "SELECT * FROM sensor_devices WHERE ward_id = ?", (ward_id,)
        )
    else:
        cursor = await db.execute("SELECT * FROM sensor_devices")
    rows = await cursor.fetchall()

    devices = []
    for row in rows:
        d = dict(row)
        # Determine freshness
        try:
            last = datetime.fromisoformat(d["last_seen"].replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
        except Exception:
            age_min = 9999

        if age_min < settings.stale_minutes:
            d["status"] = "online"
        elif age_min < settings.offline_minutes:
            d["status"] = "stale"
        else:
            d["status"] = "offline"
        d["age_min"] = round(age_min, 1)

        # Attach sparkline (last 10 readings)
        cursor2 = await db.execute(
            "SELECT water_level_cm, ts FROM sensor_readings WHERE device_id=? ORDER BY ts DESC LIMIT 10",
            (d["device_id"],),
        )
        spark = await cursor2.fetchall()
        d["sparkline"] = [{"level": r["water_level_cm"], "ts": r["ts"]} for r in reversed(spark)]
        devices.append(d)

    return {"devices": devices, "count": len(devices)}


def _compute_ror(rows) -> float:
    """
    Rate of rise in cm per 5 minutes, computed from the ACTUAL timestamps
    of the oldest and newest readings in the window.

    Bug fix (v0.2): the previous implementation hardcoded elapsed_s = n * 10,
    assuming readings were exactly 10 s apart. Real readings arrive at
    irregular intervals (network jitter, sensor sleep cycles, CCTV frames,
    manual submissions). This version parses the `ts` field of the oldest and
    newest rows and uses the real wall-clock elapsed seconds, so ror is correct
    regardless of inter-reading cadence.

    Edge cases handled:
    - Fewer than 2 rows: returns 0.0 (not enough data).
    - All timestamps identical (elapsed_s == 0): returns 0.0 (no divide-by-zero).
    - Negative delta (level fell): returns 0.0 (ror cannot be negative).
    """
    if len(rows) < 2:
        return 0.0
    try:
        # rows are newest-first (ORDER BY ts DESC)
        levels = [r["water_level_cm"] for r in rows]
        ts_strs = [r["ts"] for r in rows]

        delta_cm = levels[0] - levels[-1]   # newest_level - oldest_level

        # Parse real timestamps from ISO-8601 strings
        def _parse(ts_str: str) -> datetime:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

        newest_dt = _parse(ts_strs[0])
        oldest_dt = _parse(ts_strs[-1])
        elapsed_s = (newest_dt - oldest_dt).total_seconds()

        # Guard: all timestamps identical -> no elapsed time -> rate is 0
        if elapsed_s <= 0:
            return 0.0

        # Normalise to 5 minutes (300 s); clamp to >= 0
        return max(0.0, round(delta_cm * 300.0 / elapsed_s, 2))
    except Exception:
        return 0.0


def _derive_ward_id(lat: float | None, lon: float | None) -> str | None:
    """
    Derive the ward_id from a lat/lon by checking which ward's bbox contains
    the point. Returns the first matching ward_id, or None if outside all wards.
    Falls back gracefully if wards.json is missing (uses legacy ward.json).
    """
    if lat is None or lon is None:
        return None
    try:
        import json as _json
        from pathlib import Path
        wards_path = Path(settings.data_dir) / "wards.json"
        if not wards_path.exists():
            # Fall back to legacy single-ward file
            ward_path = Path(settings.data_dir) / "ward.json"
            if ward_path.exists():
                with open(ward_path, encoding="utf-8") as f:
                    ward = _json.load(f)
                bb = ward["bbox"]
                if bb["min_lat"] <= lat <= bb["max_lat"] and bb["min_lon"] <= lon <= bb["max_lon"]:
                    return ward.get("ward_id", "kotturpuram")
            return None
        with open(wards_path, encoding="utf-8") as f:
            wards = _json.load(f)
        for ward in wards:
            bb = ward["bbox"]
            if bb["min_lat"] <= lat <= bb["max_lat"] and bb["min_lon"] <= lon <= bb["max_lon"]:
                return ward["ward_id"]
        return None
    except Exception:
        return None
