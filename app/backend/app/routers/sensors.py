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
    await db.execute(
        """INSERT INTO sensor_readings
           (device_id, ts, water_level_cm, rainfall_mm, battery_pct, rssi, lat, lon, data_source)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (reading.device_id, reading.ts, reading.water_level_cm,
         reading.rainfall_mm, reading.battery_pct, reading.rssi,
         reading.lat, reading.lon, reading.data_source),
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
        alert_reason = f"Ground sensor override: rate of rise {ror:.1f} cm/5min ≥ threshold {settings.ror_urgent_cm_per_5min}"
    if reading.water_level_cm >= settings.critical_level_cm:
        alert_active = 1
        alert_reason = f"Ground sensor override: water level {reading.water_level_cm:.0f} cm ≥ critical {settings.critical_level_cm}"

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
    }

    await db.execute(
        """INSERT OR REPLACE INTO sensor_devices
           (device_id, last_seen, last_level, rate_of_rise, battery_pct, rssi, lat, lon, status, data_source, alert_active)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (reading.device_id, reading.ts, reading.water_level_cm, ror,
         reading.battery_pct, reading.rssi, reading.lat, reading.lon,
         status, reading.data_source, alert_active),
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
    }


@router.get("/sensors")
async def get_sensors(db: aiosqlite.Connection = Depends(get_db)):
    """Return latest state of all sensor nodes."""
    now_ts = time.time()
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
    """Rate of rise in cm per 5 minutes (smoothed over last N readings)."""
    if len(rows) < 2:
        return 0.0
    try:
        levels = [r["water_level_cm"] for r in rows]
        # slope: change from oldest to newest (rows are newest-first)
        delta = levels[0] - levels[-1]   # newest - oldest
        n = len(rows) - 1
        # Each reading ~10s → n readings * 10s; normalise to 5 min (300s)
        elapsed_s = n * 10
        return max(0.0, round(delta * 300 / elapsed_s, 2)) if elapsed_s > 0 else 0.0
    except Exception:
        return 0.0
