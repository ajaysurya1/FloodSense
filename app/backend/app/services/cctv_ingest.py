"""
CCTV Ingest Service – FloodSense (PART 2)

Opens RTSP/HTTP video streams, grabs one frame every N seconds, runs the
CLIP classifier against a flood-graded label set, and POSTs the result to
/api/sensors/readings tagged data_source="CCTV".

⚠️  DISCLAIMER: depth values derived here are UNCALIBRATED VISUAL PROXIES.
    A camera image classified as "ankle-deep flooding" does NOT guarantee
    a measured water depth of 15 cm — the road may be significantly deeper
    or shallower. These estimates exist to supplement (not replace) physical
    IoT sensors and citizen reports. See config.yaml cctv.depth_proxy_cm for
    the label→cm mapping, which is explicitly labelled ASSUMPTION.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── CCTV label set (expanded from citizen-report labels) ─────────────────────
_CCTV_LABELS = [
    "a dry road",
    "a road with light standing water",
    "a road with ankle-deep flooding",
    "a road with knee-deep or deeper flooding",
    "no visible road, obstructed view",
]

# ── In-memory camera status registry ─────────────────────────────────────────
# { camera_id: { "status": "online"|"offline", "last_seen": iso_str|None,
#                "last_label": str|None, "last_level_cm": int|None,
#                "last_score": float|None, "error": str|None } }
_camera_status: dict[str, dict[str, Any]] = {}


def get_camera_status() -> dict[str, dict[str, Any]]:
    """Return a copy of the current camera status registry."""
    return dict(_camera_status)


def _load_cameras() -> list[dict]:
    cameras_path = Path(settings.cctv_cameras_file)
    if not cameras_path.exists():
        logger.warning("cameras.json not found at %s – CCTV ingest disabled.", cameras_path)
        return []
    with open(cameras_path, encoding="utf-8") as f:
        return json.load(f)


def _depth_proxy(label: str) -> int | None:
    """
    Map a CLIP label to an approximate water_level_cm proxy.
    Returns None if the label should be skipped (e.g. obstructed view).
    """
    mapping: dict[str, int] = settings.cctv_depth_proxy
    val = mapping.get(label, None)
    if val is None:
        # Label not in mapping – skip
        return None
    if val == -1:
        # Sentinel: obstructed view – do not post a reading
        return None
    return val


async def _classify_frame(frame_bytes: bytes) -> dict:
    """
    Run CLIP inference against the CCTV label set.
    Falls back gracefully if CLIP is unavailable.
    """
    # Import the shared CLIP classifier service and temporarily swap labels
    from app.services import clip_classifier as _cc

    if not _cc._READY or _cc._model is None:
        return {
            "label": "needs_manual_review",
            "score": 0.0,
            "source": "manual_review",
        }

    try:
        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
        loop = asyncio.get_event_loop()

        def _run():
            inputs = _cc._processor(
                text=_CCTV_LABELS,
                images=img,
                return_tensors="pt",
                padding=True,
            )
            with torch.no_grad():
                outputs = _cc._model(**inputs)
                logits = outputs.logits_per_image[0]
                probs = logits.softmax(dim=0).tolist()
            best_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
            return {
                "label": _CCTV_LABELS[best_idx],
                "score": round(probs[best_idx], 4),
                "source": "CLIP",
            }

        return await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("CCTV CLIP inference error: %s", e)
        return {"label": "needs_manual_review", "score": 0.0, "source": "manual_review"}


async def _grab_frame_cv2(stream_url: str) -> bytes | None:
    """
    Grab one frame from an RTSP/HTTP stream using OpenCV.
    Returns raw JPEG bytes, or None on failure.
    """
    try:
        import cv2  # type: ignore
        import numpy as np

        def _read():
            cap = cv2.VideoCapture(stream_url)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", frame)
            return bytes(buf) if ok else None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read)
    except ImportError:
        logger.warning("opencv-python not installed – cannot grab frames from %s", stream_url)
        return None
    except Exception as e:
        logger.error("Frame grab error for %s: %s", stream_url, e)
        return None


async def _post_reading(camera: dict, level_cm: int, label: str) -> None:
    """POST the derived water_level_cm to /api/sensors/readings as a CCTV virtual sensor."""
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "device_id": f"cctv_{camera['camera_id']}",
        "ts": ts,
        "water_level_cm": float(level_cm),
        "data_source": "CCTV",
        "lat": camera.get("lat"),
        "lon": camera.get("lon"),
    }
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            r = await client.post("/api/sensors/readings", json=payload, timeout=5.0)
            r.raise_for_status()
            logger.debug(
                "CCTV %s → label=%r level=%d cm posted (status %d)",
                camera["camera_id"], label, level_cm, r.status_code,
            )
    except Exception as e:
        logger.warning("CCTV POST failed for %s: %s", camera["camera_id"], e)


async def _ingest_camera(camera: dict) -> None:
    """
    Single camera ingest cycle:
    1. Grab one frame.
    2. Classify with CLIP.
    3. Map label → depth proxy.
    4. POST to /api/sensors/readings.
    5. Update status registry.
    """
    cam_id = camera["camera_id"]
    stream_url = camera["stream_url"]

    frame_bytes = await _grab_frame_cv2(stream_url)
    if frame_bytes is None:
        _camera_status[cam_id] = {
            **_camera_status.get(cam_id, {}),
            "status": "offline",
            "error": "Could not open stream or grab frame",
            "last_seen": _camera_status.get(cam_id, {}).get("last_seen"),
        }
        return

    result = await _classify_frame(frame_bytes)
    label = result["label"]
    score = result["score"]
    level_cm = _depth_proxy(label)

    now = datetime.now(timezone.utc).isoformat()
    _camera_status[cam_id] = {
        "status": "online",
        "last_seen": now,
        "last_label": label,
        "last_label_score": score,
        "last_level_cm": level_cm,  # None if obstructed / no mapping
        "error": None,
        "camera_label": camera.get("label", cam_id),
        "ward_id": camera.get("ward_id"),
        "lat": camera.get("lat"),
        "lon": camera.get("lon"),
        "disclaimer": (
            "⚠️ Depth value is an UNCALIBRATED VISUAL PROXY derived from a camera "
            "image – NOT a measured water depth. See config.yaml cctv.depth_proxy_cm "
            "(ASSUMPTION)."
        ),
    }

    if level_cm is not None:
        await _post_reading(camera, level_cm, label)
    else:
        logger.debug(
            "CCTV %s label=%r → skipped posting (obstructed or no mapping)", cam_id, label
        )


async def _camera_loop(camera: dict) -> None:
    """
    Continuous ingest loop for a single camera.
    Retries on failure without crashing the overall loop.
    """
    cam_id = camera["camera_id"]
    poll = settings.cctv_poll_interval_s
    retry = settings.cctv_retry_interval_s

    # Initialise status entry
    _camera_status[cam_id] = {
        "status": "initialising",
        "last_seen": None,
        "last_label": None,
        "last_level_cm": None,
        "error": None,
        "camera_label": camera.get("label", cam_id),
        "ward_id": camera.get("ward_id"),
    }

    while True:
        try:
            await _ingest_camera(camera)
            await asyncio.sleep(poll)
        except asyncio.CancelledError:
            logger.info("CCTV loop cancelled for %s", cam_id)
            break
        except Exception as e:
            logger.error("Unexpected error in CCTV loop for %s: %s – retrying in %ds", cam_id, e, retry)
            _camera_status[cam_id] = {
                **_camera_status.get(cam_id, {}),
                "status": "offline",
                "error": str(e),
            }
            await asyncio.sleep(retry)


async def start_ingest_loop() -> None:
    """
    Start one asyncio task per camera defined in cameras.json.
    Non-blocking: individual camera failures never crash the loop.
    Called from main.py lifespan at startup.
    """
    cameras = _load_cameras()
    if not cameras:
        logger.info("No cameras configured – CCTV ingest idle.")
        return
    logger.info("Starting CCTV ingest for %d camera(s).", len(cameras))
    tasks = [asyncio.create_task(_camera_loop(cam)) for cam in cameras]
    # Let tasks run in the background; we don't await them here.
    _ = tasks  # suppress "unused variable" linting warning
