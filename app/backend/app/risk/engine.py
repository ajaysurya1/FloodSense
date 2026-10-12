"""
Risk Engine (D1) – FloodSense

Computes per-cell flood risk scores for the selected ward.

WARNING: ALL outputs are heuristic, uncalibrated estimates.
    Weights in config.yaml are ASSUMPTIONS not calibrated parameters.
    Do NOT use for life-safety decisions without expert validation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings
from app.services import open_meteo, elevation_service
from app.services.sensor_state import get_latest_sensor_state

logger = logging.getLogger(__name__)

# ── Ward + seed data ──────────────────────────────────────────────────────────
_DATA = Path(settings.data_dir)


def _load_wards() -> list[dict]:
    """Load all wards. Falls back to legacy ward.json if wards.json absent."""
    wards_path = _DATA / "wards.json"
    if wards_path.exists():
        with open(wards_path, encoding="utf-8") as f:
            return json.load(f)
    # Legacy single-ward fallback
    ward_path = _DATA / "ward.json"
    with open(ward_path, encoding="utf-8") as f:
        ward = json.load(f)
    if "ward_id" not in ward:
        ward["ward_id"] = "kotturpuram"
    return [ward]


def _load_ward(ward_id: str | None) -> dict:
    """Return the ward dict for the given ward_id, defaulting to the first ward."""
    wards = _load_wards()
    if not ward_id:
        return wards[0]
    for w in wards:
        if w.get("ward_id") == ward_id:
            return w
    logger.warning("ward_id '%s' not found; falling back to first ward.", ward_id)
    return wards[0]


def _load_hotspots(ward_id: str | None) -> list:
    """
    Load hotspot features for the given ward.

    Strategy: we add a ward_id property to each feature in the shared
    hotspots.geojson files, then filter here.  This is less error-prone
    than splitting into per-ward files when the seed dataset is small and
    features already have explicit coordinates.  The trade-off is one extra
    JSON scan per request, which is negligible for demo-scale data.
    """
    # Try per-ward file first (future-proof)
    if ward_id:
        per_ward = _DATA / f"hotspots_{ward_id}.geojson"
        if per_ward.exists():
            with open(per_ward, encoding="utf-8") as f:
                fc = json.load(f)
            return [feat["geometry"]["coordinates"] + [feat["properties"]["risk_class"]]
                    for feat in fc["features"]]

    # Fall back to shared file; filter by ward_id property if present
    path = _DATA / "hotspots.geojson"
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc["features"]
    if ward_id:
        features = [f for f in features
                    if f["properties"].get("ward_id", ward_id) == ward_id]
    return [feat["geometry"]["coordinates"] + [feat["properties"]["risk_class"]]
            for feat in features]


def _load_drains(ward_id: str | None) -> list[dict]:
    """Load drain features for the given ward (same strategy as hotspots)."""
    if ward_id:
        per_ward = _DATA / f"drains_{ward_id}.geojson"
        if per_ward.exists():
            with open(per_ward, encoding="utf-8") as f:
                fc = json.load(f)
            return fc["features"]

    path = _DATA / "drains.geojson"
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc["features"]
    if ward_id:
        features = [f for f in features
                    if f["properties"].get("ward_id", ward_id) == ward_id]
    return features


def _load_facilities(ward_id: str | None) -> list[dict]:
    """Load facility features for the given ward."""
    if ward_id:
        per_ward = _DATA / f"facilities_{ward_id}.geojson"
        if per_ward.exists():
            with open(per_ward, encoding="utf-8") as f:
                fc = json.load(f)
            return fc["features"]

    path = _DATA / "facilities.geojson"
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc["features"]
    if ward_id:
        features = [f for f in features
                    if f["properties"].get("ward_id", ward_id) == ward_id]
    return features


# ── Grid generation ───────────────────────────────────────────────────────────
def _generate_grid(ward: dict, cell_m: int) -> list[dict]:
    """Return list of cell dicts with centre lat/lon."""
    bb = ward["bbox"]
    lat_c = (bb["min_lat"] + bb["max_lat"]) / 2
    deg_lat = cell_m / 111_320
    deg_lon = cell_m / (111_320 * math.cos(math.radians(lat_c)))

    cells = []
    lat = bb["min_lat"] + deg_lat / 2
    row = 0
    while lat < bb["max_lat"]:
        lon = bb["min_lon"] + deg_lon / 2
        col = 0
        while lon < bb["max_lon"]:
            cells.append({"lat": lat, "lon": lon, "row": row, "col": col})
            lon += deg_lon
            col += 1
        lat += deg_lat
        row += 1
    return cells


# ── Distance helper ───────────────────────────────────────────────────────────
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# ── Hotspot proximity score ───────────────────────────────────────────────────
def _hotspot_score(lat: float, lon: float, hotspots: list) -> float:
    if not hotspots:
        return 0.0
    class_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    best = 0.0
    for hs in hotspots:
        hs_lon, hs_lat, cls = hs
        d = _haversine_km(lat, lon, hs_lat, hs_lon)
        influence = class_map.get(cls, 0.5) * math.exp(-d / 0.3)  # 300 m decay
        best = max(best, influence)
    return min(best, 1.0)


# ── Drainage penalty ─────────────────────────────────────────────────────────
def _drain_penalty(lat: float, lon: float, drains: list[dict]) -> float:
    cap_map = {"low": 1.0, "medium": 0.5, "high": 0.1}
    penalty = 0.0
    for feat in drains:
        d_lon, d_lat = feat["geometry"]["coordinates"]
        d = _haversine_km(lat, lon, d_lat, d_lon)
        if d < 0.4:  # 400 m influence
            cap_pen = cap_map.get(feat["properties"]["capacity_class"], 0.5)
            blocked_bonus = 0.3 if feat["properties"].get("blocked") else 0.0
            penalty = max(penalty, (cap_pen + blocked_bonus) * math.exp(-d / 0.2))
    return min(penalty, 1.0)


# ── Onset window ─────────────────────────────────────────────────────────────
def _onset_window(score: float, horizon_min: int) -> str:
    if score < settings.th_watch:
        return "No imminent onset"
    frac = (score - settings.th_watch) / (100 - settings.th_watch)
    lo = max(15, int(horizon_min * (1 - frac)))
    hi = lo + 45
    return f"{lo}–{hi} min"


# ── Confidence rules ──────────────────────────────────────────────────────────
def _confidence(
    has_nearby_sensor: bool,
    forecast_age_min: float,
    rain_mm: float,
    elev_ok: bool,
) -> tuple[str, list[str]]:
    reasons = []
    score = 3  # start at High
    if not has_nearby_sensor:
        score -= 1
        reasons.append("No ground sensor within 1 km (ASSUMPTION threshold)")
    if forecast_age_min > settings.forecast_cache_minutes:
        score -= 1
        reasons.append(f"Forecast data is {forecast_age_min:.0f} min old (stale)")
    if not elev_ok:
        score -= 1
        reasons.append("Elevation data from cache, not live API")
    if rain_mm < 0.5:
        score -= 1
        reasons.append("Very low rainfall – risk driven by terrain/hotspot proximity")
    level = ["Low", "Low", "Medium", "High"][max(0, min(score, 3))]
    return level, reasons


# ── Scenario data (SIMULATED storm) ──────────────────────────────────────────
def _scenario_rain(lat: float, lon: float, horizon_min: int, ward: dict) -> dict:
    """
    Return simulated rainfall mimicking a northeast-monsoon squall.

    Bug fix (v0.2, Part 1): epicentre is now ward-relative (offset from the
    ward's centre), not hardcoded to a fixed Adyar lat/lon.  This ensures
    SCENARIO mode is meaningful for every ward, not just Kotturpuram.
    """
    centre = ward.get("centre", {"lat": 13.0070, "lon": 80.2510})
    # Place storm epicentre 0.8 km south-east of ward centre (ASSUMPTION)
    epic_lat = centre["lat"] - 0.008
    epic_lon = centre["lon"] + 0.008
    d = _haversine_km(lat, lon, epic_lat, epic_lon)
    base = max(0.0, 45.0 - d * 80)           # up to 45 mm/3h near epicentre
    intensity = base * (1 + 0.3 * math.sin(time.time() / 60))  # gentle pulse
    cumulative = intensity * (horizon_min / 60)
    return {
        "intensity_mm_3h": round(intensity, 2),
        "cumulative_mm": round(cumulative, 2),
        "source": "SIMULATED",
        "age_min": 0,
    }


# ── Main risk computation ─────────────────────────────────────────────────────
async def compute_risk(horizon_min: int = 60, ward_id: str | None = None) -> dict:
    """
    Compute per-cell risk GeoJSON for the given ward.
    Returns FeatureCollection with properties per cell.
    All scores are heuristic, uncalibrated estimates.
    """
    ward = _load_ward(ward_id)
    effective_ward_id = ward.get("ward_id", ward_id)
    hotspots = _load_hotspots(effective_ward_id)
    drains = _load_drains(effective_ward_id)

    cells = _generate_grid(ward, 150)  # 150m cell size – configurable in config.yaml

    # Fetch elevation (cached; keyed by lat/lon, ward-agnostic)
    lats = [c["lat"] for c in cells]
    lons = [c["lon"] for c in cells]
    elevations, elev_from_cache = await elevation_service.get_elevations(lats, lons)

    # Compute terrain lowness
    # Bug fix (v0.2): previously silently fell back to reshape(-1, 1) when
    # counts didn't match, producing meaningless terrain_lowness values.
    # Now: log a clear warning and set terrain_lowness to all zeros for safety.
    elev_arr = np.array(elevations)
    terrain_lowness = np.zeros(len(cells))
    cols_set = max(c["col"] for c in cells) + 1
    rows_set = max(c["row"] for c in cells) + 1
    expected_count = rows_set * cols_set
    actual_count = len(elev_arr)

    if actual_count != expected_count:
        logger.warning(
            "Terrain grid mismatch for ward '%s': expected %d cells (%dx%d) "
            "but got %d elevation values. Setting terrain_lowness to flat 0 "
            "for this request rather than computing nonsense.",
            effective_ward_id, expected_count, rows_set, cols_set, actual_count,
        )
        # terrain_lowness already initialised to zeros — nothing more to do
    else:
        grid_elev = elev_arr.reshape(rows_set, cols_set)
        for i, cell in enumerate(cells):
            r, c_idx = cell["row"], cell["col"]
            neighbours = []
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c_idx + dc
                    if 0 <= nr < rows_set and 0 <= nc < cols_set and (dr != 0 or dc != 0):
                        neighbours.append(grid_elev[nr, nc])
            if neighbours:
                terrain_lowness[i] = max(0.0, float(np.mean(neighbours)) - grid_elev[r, c_idx])
            else:
                terrain_lowness[i] = 0.0
        # Normalise terrain_lowness to 0-1
        tl_max = terrain_lowness.max()
        if tl_max > 0:
            terrain_lowness = terrain_lowness / tl_max

    # Fetch latest sensor state for rate-of-rise modifier
    sensors = await get_latest_sensor_state()

    # Fetch forecast or use scenario
    use_scenario = settings.mode == "SCENARIO"

    forecast_cache = {}
    if not use_scenario:
        unique_coords = {(round(c["lat"], 2), round(c["lon"], 2)) for c in cells}
        for clat, clon in unique_coords:
            forecast_cache[(clat, clon)] = await open_meteo.get_forecast(clat, clon, horizon_min)

    features = []
    for i, cell in enumerate(cells):
        lat, lon = cell["lat"], cell["lon"]

        # ── Rain ──
        if use_scenario:
            rain_data = _scenario_rain(lat, lon, horizon_min, ward)
        else:
            rain_data = forecast_cache.get((round(lat, 2), round(lon, 2))) or await open_meteo.get_forecast(lat, lon, horizon_min)

        rain_intensity_norm = min(rain_data["intensity_mm_3h"] / 50.0, 1.0)   # 50mm/3h = extreme
        cumulative_norm     = min(rain_data["cumulative_mm"] / 100.0, 1.0)     # 100mm cumul = extreme

        # ── Terrain ──
        tl_norm = float(terrain_lowness[i])

        # ── Hotspot ──
        hs_score = _hotspot_score(lat, lon, hotspots)

        # ── Drainage ──
        dr_pen = _drain_penalty(lat, lon, drains)

        # ── Sensor rate-of-rise ──
        ror_norm = 0.0
        nearby_sensor = None
        for s in sensors.values():
            if s.get("lat") and s.get("lon"):
                d = _haversine_km(lat, lon, s["lat"], s["lon"])
                if d < 1.0:
                    ror = s.get("rate_of_rise", 0.0)
                    ror_norm = max(ror_norm, min(ror / 10.0, 1.0))  # 10 cm/5min = extreme
                    nearby_sensor = s["device_id"]

        # ── Weighted score ──
        score = (
            settings.w_rain_intensity   * rain_intensity_norm * 100 +
            settings.w_cumulative_rain  * cumulative_norm     * 100 +
            settings.w_terrain_lowness  * tl_norm             * 100 +
            settings.w_hotspot_prox     * hs_score            * 100 +
            settings.w_drainage_penalty * dr_pen              * 100 +
            settings.w_sensor_ror       * ror_norm            * 100
        )
        score = round(min(score, 100), 1)

        # ── Severity ──
        if score >= settings.th_severe:
            severity = "Severe"
        elif score >= settings.th_warning:
            severity = "Warning"
        elif score >= settings.th_watch:
            severity = "Watch"
        else:
            severity = "Normal"

        # ── Confidence ──
        conf, conf_reasons = _confidence(
            has_nearby_sensor=nearby_sensor is not None,
            forecast_age_min=rain_data.get("age_min", 0),
            rain_mm=rain_data["intensity_mm_3h"],
            elev_ok=not elev_from_cache,
        )

        # ── Plain-language reasons ──
        reasons = []
        if rain_intensity_norm > 0.3:
            reasons.append(f"High rainfall intensity ({rain_data['intensity_mm_3h']:.1f} mm/3h, {rain_data['source']})")
        if cumulative_norm > 0.2:
            reasons.append(f"Significant cumulative rainfall ({rain_data['cumulative_mm']:.1f} mm)")
        if tl_norm > 0.3:
            reasons.append("Terrain analysis shows this is a low-lying depression (SEED elevation)")
        if hs_score > 0.4:
            reasons.append("Near a historically flood-prone location (SEED hotspot data)")
        if dr_pen > 0.4:
            reasons.append("Nearby drain has low capacity or is blocked (SEED drain data)")
        if ror_norm > 0.3:
            reasons.append(f"Ground sensor {nearby_sensor} shows rapid water rise")
        if not reasons:
            reasons.append("Low risk from all components")

        # ── Cell polygon ──
        bb = ward["bbox"]
        lat_c = (bb["min_lat"] + bb["max_lat"]) / 2
        half_lat = (150 / 111_320) / 2
        half_lon = (150 / (111_320 * math.cos(math.radians(lat_c)))) / 2

        bbox_coords = [
            [lon - half_lon, lat - half_lat],
            [lon + half_lon, lat - half_lat],
            [lon + half_lon, lat + half_lat],
            [lon - half_lon, lat + half_lat],
            [lon - half_lon, lat - half_lat],
        ]

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [bbox_coords]},
            "properties": {
                "cell_id": f"r{cell['row']}_c{cell['col']}",
                "lat": lat,
                "lon": lon,
                "score": score,
                "severity": severity,
                "onset_window": _onset_window(score, horizon_min),
                "confidence": conf,
                "confidence_notes": conf_reasons,
                "reasons": reasons,
                "rain_intensity_mm_3h": rain_data["intensity_mm_3h"],
                "cumulative_rain_mm": rain_data["cumulative_mm"],
                "terrain_lowness_norm": round(float(tl_norm), 3),
                "hotspot_score": round(hs_score, 3),
                "drainage_penalty": round(dr_pen, 3),
                "sensor_ror_norm": round(ror_norm, 3),
                "nearby_sensor": nearby_sensor,
                "elevation_m": round(float(elevations[i]), 1),
                "forecast_source": rain_data["source"],
                "elev_from_cache": elev_from_cache,
                "ward_id": effective_ward_id,
                "disclaimer": (
                    "WARNING: Heuristic, uncalibrated risk estimate. "
                    "Complements NDMA SACHET; does not replace official warnings."
                ),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "ward": ward["name"],
            "ward_id": effective_ward_id,
            "horizon_min": horizon_min,
            "mode": settings.mode,
            "cell_count": len(features),
            "disclaimer": (
                "All scores are heuristic, uncalibrated estimates. "
                "Data sources: Open-Meteo forecast (LIVE/SCENARIO), "
                "terrain SRTM (SEED cache), hotspots (SEED), drains (SEED)."
            ),
        },
    }
