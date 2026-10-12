"""Central settings – reads config.yaml, overridable via env vars."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_config() -> Path:
    candidates = [
        Path(__file__).parent.parent.parent / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
        Path("config.yaml"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return candidates[0].resolve()

_CONFIG_PATH = _find_config()
with open(_CONFIG_PATH) as _f:
    _RAW = yaml.safe_load(_f)

def _find_data_dir() -> Path:
    candidates = [
        Path(__file__).parent.parent.parent.parent / "data",
        Path(__file__).parent.parent.parent / "data",
        Path("data"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return candidates[0].resolve()

_DATA_DIR = _find_data_dir()
_DB_PATH  = _DATA_DIR / "floodsense.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOODSENSE_")

    mode: Literal["LIVE", "SCENARIO"] = os.environ.get("FLOODSENSE_MODE", _RAW["mode"])  # type: ignore[assignment]
    data_dir: str = str(_DATA_DIR)
    db_path:  str = str(_DB_PATH)

    # risk weights
    w_rain_intensity:   float = _RAW["risk_weights"]["rain_intensity_next_3h"]
    w_cumulative_rain:  float = _RAW["risk_weights"]["cumulative_rain"]
    w_terrain_lowness:  float = _RAW["risk_weights"]["terrain_lowness"]
    w_hotspot_prox:     float = _RAW["risk_weights"]["hotspot_proximity"]
    w_drainage_penalty: float = _RAW["risk_weights"]["drainage_penalty"]
    w_sensor_ror:       float = _RAW["risk_weights"]["sensor_rate_of_rise"]

    # severity thresholds
    th_watch:   float = _RAW["severity_thresholds"]["watch"]
    th_warning: float = _RAW["severity_thresholds"]["warning"]
    th_severe:  float = _RAW["severity_thresholds"]["severe"]

    # sensor
    ror_urgent_cm_per_5min: float = _RAW["sensor"]["rate_of_rise_urgent_cm_per_5min"]
    critical_level_cm:      float = _RAW["sensor"]["critical_level_cm"]
    stale_minutes:          int   = _RAW["sensor"]["stale_minutes"]
    offline_minutes:        int   = _RAW["sensor"]["offline_minutes"]
    smoothing_readings:     int   = _RAW["sensor"]["smoothing_readings"]

    # forecast
    forecast_cache_minutes: int = _RAW["forecast"]["cache_minutes"]

    # elevation
    terrain_cache_file: str = str(_DATA_DIR / "terrain_cache.json")

    # alert templates
    template_file: str = str(_DATA_DIR / "templates" / "alert_templates.yaml")

    # CCTV
    cctv_poll_interval_s: int   = _RAW.get("cctv", {}).get("poll_interval_s", 15)
    cctv_retry_interval_s: int  = _RAW.get("cctv", {}).get("retry_interval_s", 60)
    cctv_cameras_file: str      = str(_DATA_DIR / "cameras.json")
    # Depth proxy map: label str -> cm (-1 = skip posting)
    cctv_depth_proxy: dict      = _RAW.get("cctv", {}).get("depth_proxy_cm", {
        "a dry road": 0,
        "a road with light standing water": 5,
        "a road with ankle-deep flooding": 15,
        "a road with knee-deep or deeper flooding": 35,
        "no visible road, obstructed view": -1,
    })


settings = Settings()
