"""D7 – Municipal Dashboard router."""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.database import get_db
from app.risk.engine import compute_risk

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(
    horizon: int = 60,
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Ranked list of high-risk cells, flagged facilities, report counts, sensor alerts.
    All risk values are heuristic, uncalibrated estimates.
    """
    # Risk cells
    risk_geojson = await compute_risk(horizon_min=horizon)
    cells = risk_geojson["features"]

    # Sort by score descending, keep top 20
    top_cells = sorted(cells, key=lambda f: f["properties"]["score"], reverse=True)[:20]

    # Load facilities
    facilities_path = Path(settings.data_dir) / "facilities.geojson"
    with open(facilities_path) as f:
        facilities_fc = json.load(f)

    # Flag facilities inside high-risk cells (score ≥ watch threshold)
    def _in_bbox(fac_lon, fac_lat, cell_coords):
        lons = [c[0] for c in cell_coords[0]]
        lats = [c[1] for c in cell_coords[0]]
        return min(lons) <= fac_lon <= max(lons) and min(lats) <= fac_lat <= max(lats)

    flagged_facilities = []
    for feat in facilities_fc["features"]:
        fac_lon, fac_lat = feat["geometry"]["coordinates"]
        for cell in top_cells:
            score = cell["properties"]["score"]
            if score >= settings.th_watch:
                if _in_bbox(fac_lon, fac_lat, cell["geometry"]["coordinates"]):
                    flagged_facilities.append({
                        **feat["properties"],
                        "lat": fac_lat,
                        "lon": fac_lon,
                        "risk_score": score,
                        "severity": cell["properties"]["severity"],
                    })
                    break

    # Report counts
    cursor = await db.execute(
        "SELECT status, count(*) as cnt FROM citizen_reports GROUP BY status"
    )
    report_counts = {row["status"]: row["cnt"] for row in await cursor.fetchall()}

    # Sensor alerts
    cursor = await db.execute(
        "SELECT device_id, last_level, rate_of_rise, status, alert_active, data_source FROM sensor_devices"
    )
    sensor_rows = [dict(r) for r in await cursor.fetchall()]
    active_sensor_alerts = [s for s in sensor_rows if s.get("alert_active")]

    # Recommended actions per top cell
    actions_per_cell = []
    for cell in top_cells[:10]:
        p = cell["properties"]
        if p["score"] < settings.th_watch:
            continue
        actions = []
        if p["drainage_penalty"] > 0.4:
            actions.append(f"Inspect and clear drains near cell {p['cell_id']} (drainage penalty: {p['drainage_penalty']:.2f})")
        if p["hotspot_score"] > 0.4:
            actions.append(f"Pre-position pump near historical hotspot (score: {p['hotspot_score']:.2f})")
        if p["rain_intensity_mm_3h"] > 20:
            actions.append(f"Consider road closure advisory for low-lying roads (rain: {p['rain_intensity_mm_3h']:.1f} mm/3h)")
        if p.get("nearby_sensor"):
            actions.append(f"Monitor sensor {p['nearby_sensor']} closely")
        if not actions:
            actions.append("Monitor conditions")
        actions_per_cell.append({
            "cell_id": p["cell_id"],
            "score": p["score"],
            "severity": p["severity"],
            "onset_window": p["onset_window"],
            "confidence": p["confidence"],
            "reasons": p["reasons"],
            "actions": actions,
            "nearby_sensor": p.get("nearby_sensor"),
        })

    return {
        "top_risk_cells": actions_per_cell,
        "flagged_facilities": flagged_facilities,
        "report_counts": report_counts,
        "active_sensor_alerts": active_sensor_alerts,
        "disclaimer": (
            "All risk values are heuristic, uncalibrated estimates. "
            "Data sources: Open-Meteo (LIVE), terrain/hotspots/facilities (SEED), sensors (SIMULATED). "
            "Complements NDMA SACHET; does not replace official warnings."
        ),
    }
