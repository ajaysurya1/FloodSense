"""D4 – Citizen Reports router."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.core.config import settings
from app.core.database import get_db
from app.services import clip_classifier

router = APIRouter()

_REPORTS_DIR = Path(settings.data_dir) / "report_images"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(max(0.0, a)))


async def _check_duplicate(db, phash: str, lat: float, lon: float, ts: str) -> int | None:
    """Return duplicate parent report id if one exists within 100m & 30min."""
    try:
        cursor = await db.execute(
            "SELECT id, lat, lon, ts, phash FROM citizen_reports WHERE status != 'duplicate' ORDER BY created_at DESC LIMIT 100"
        )
        rows = await cursor.fetchall()
        for row in rows:
            if row["phash"] and row["phash"] == phash:
                return row["id"]
            d = _haversine_km(lat, lon, row["lat"], row["lon"])
            dt = abs((datetime.fromisoformat(ts.replace("Z", "+00:00")) -
                      datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))).total_seconds())
            if d < 0.1 and dt < 1800:
                return row["id"]
    except Exception:
        pass
    return None


async def _check_corroboration(db, lat: float, lon: float) -> str:
    """Return 'corroborated', 'emerging', or 'unverified'."""
    try:
        # Check against hotspot proximity (SEED data)
        import json as _json
        hotspots_path = Path(settings.data_dir) / "hotspots.geojson"
        with open(hotspots_path, encoding="utf-8") as f:
            hs_data = _json.load(f)
        for feat in hs_data["features"]:
            hs_lon, hs_lat = feat["geometry"]["coordinates"]
            if _haversine_km(lat, lon, hs_lat, hs_lon) < 0.3:
                return "corroborated"

        # Check physical sensor rate-of-rise (> 1.0 cm/5min) OR nearby CCTV virtual sensor showing flood-like frames
        from app.services.sensor_state import get_latest_sensor_state
        sensors = await get_latest_sensor_state()
        for s in sensors.values():
            if s.get("lat") and s.get("lon"):
                dist = _haversine_km(lat, lon, s["lat"], s["lon"])
                if dist < 0.5:
                    # Physical sensor with high rate of rise or high water level
                    if s.get("rate_of_rise", 0) > 1.0 or s.get("water_level_cm", 0) > 30.0:
                        return "corroborated"
                    # CCTV sensor showing flood-like frames (uncalibrated visual proxy > 0)
                    if s.get("data_source") == "CCTV" and s.get("water_level_cm", 0) > 0:
                        return "corroborated"

        # Also check CCTV camera status directly
        from app.services.cctv_ingest import get_camera_status
        cam_statuses = get_camera_status()
        for c in cam_statuses.values():
            if c.get("lat") and c.get("lon"):
                if _haversine_km(lat, lon, c["lat"], c["lon"]) < 0.5:
                    if (c.get("last_level_cm") or 0) > 0:
                        return "corroborated"

        # Check for emerging cluster (3+ reports within 300 m in 20 min)
        cursor = await db.execute(
            "SELECT lat, lon, ts FROM citizen_reports WHERE status NOT IN ('duplicate','flagged') ORDER BY created_at DESC LIMIT 50"
        )
        rows = await cursor.fetchall()
        now_ts = datetime.now(timezone.utc)
        cluster = 0
        for row in rows:
            d = _haversine_km(lat, lon, row["lat"], row["lon"])
            try:
                row_ts = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
                dt = abs((now_ts - row_ts).total_seconds())
            except Exception:
                dt = 9999
            if d < 0.3 and dt < 1200:
                cluster += 1
        if cluster >= 2:  # this report is the 3rd
            return "emerging"

        return "unverified"
    except Exception:
        return "unverified"


@router.post("/reports")
async def submit_report(
    lat: float = Form(...),
    lon: float = Form(...),
    report_type: str = Form(...),
    ts: str = Form(default=""),
    note: str = Form(default=""),
    image: UploadFile | None = File(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Submit a citizen flood report.
    Images are classified with CLIP (zero-shot). Suspicious reports go to review queue.
    Reports are NEVER used to claim measured flood depth.
    """
    ts = ts or datetime.now(timezone.utc).isoformat()
    # Derive ward_id server-side; never trust client to send it
    from app.routers.sensors import _derive_ward_id
    ward_id = _derive_ward_id(lat, lon)

    image_bytes = None
    image_path = None
    phash_str = None
    clip_label = "no_image"
    clip_score = 0.0
    flags = []

    if image:
        image_bytes = await image.read()
        # Save image
        fname = f"{hashlib.md5(image_bytes).hexdigest()[:12]}.jpg"
        img_path = _REPORTS_DIR / fname
        with open(img_path, "wb") as f:
            f.write(image_bytes)
        image_path = str(img_path)

        # Perceptual hash
        try:
            import imagehash
            from PIL import Image as PILImage
            pil = PILImage.open(io.BytesIO(image_bytes))
            phash_str = str(imagehash.phash(pil))
        except Exception:
            phash_str = hashlib.md5(image_bytes).hexdigest()[:16]

        # CLIP classification
        result = await clip_classifier.classify(image_bytes)
        clip_label = result["label"]
        clip_score = result["score"]

        # Suspicious flags
        if clip_classifier.is_suspicious(clip_label, clip_score):
            flags.append(f"CLIP label '{clip_label}' with score {clip_score:.2f}")

    # Duplicate check
    dup_of = await _check_duplicate(db, phash_str or "", lat, lon, ts)
    status = "duplicate" if dup_of else "pending"
    if dup_of:
        await db.execute(
            "UPDATE citizen_reports SET dup_count = dup_count + 1 WHERE id = ?", (dup_of,)
        )

    # Corroboration
    corroboration = "unverified"
    if not dup_of:
        corroboration = await _check_corroboration(db, lat, lon)

    # Suspicious → review queue
    if flags and not dup_of:
        status = "flagged"

    flags_json = json.dumps(flags) if flags else None
    cursor = await db.execute(
        """INSERT INTO citizen_reports
           (ts, lat, lon, report_type, note, image_path, clip_label, clip_score,
            phash, status, duplicate_of, corroboration, flags, ward_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ts, lat, lon, report_type, note, image_path, clip_label, clip_score,
         phash_str, status, dup_of, corroboration, flags_json, ward_id),
    )
    await db.commit()
    report_id = cursor.lastrowid

    return {
        "id": report_id,
        "status": status,
        "corroboration": corroboration,
        "clip_label": clip_label,
        "clip_score": clip_score,
        "flags": flags,
        "duplicate_of": dup_of,
        "disclaimer": (
            "Unverified citizen report. CV label and score are heuristic estimates. "
            "No depth measurement is implied."
        ),
    }


@router.get("/reports")
async def get_reports(
    limit: int = 100,
    status: str | None = None,
    ward_id: str | None = Query(None, description="Filter reports by ward"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return recent citizen reports as GeoJSON, optionally filtered by ward."""
    clauses = []
    params: list = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if ward_id:
        clauses.append("ward_id = ?")
        params.append(ward_id)
    q = "SELECT * FROM citizen_reports"
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    features = []
    for row in rows:
        d = dict(row)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [d["lon"], d["lat"]]},
            "properties": {k: v for k, v in d.items() if k not in ("lat", "lon")},
        })
    return {"type": "FeatureCollection", "features": features, "count": len(features)}
