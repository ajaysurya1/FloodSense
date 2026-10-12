"""CCTV virtual-sensor status router."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.cctv_ingest import get_camera_status

router = APIRouter()


@router.get("/cctv/status")
async def cctv_status():
    """
    Return the current status of every configured CCTV camera.

    Fields per camera:
      - status: 'online' | 'offline' | 'initialising'
      - last_seen: ISO timestamp of last successful frame grab (or null)
      - last_label: CLIP classification label (e.g. 'a dry road')
      - last_label_score: softmax probability of that label (0–1)
      - last_level_cm: depth proxy value in cm (null if obstructed/no mapping)
      - error: error message if offline (null otherwise)
      - disclaimer: reminder that depth_cm is an UNCALIBRATED VISUAL PROXY

    ⚠️  All depth values are uncalibrated visual proxies, NOT measured depths.
    """
    statuses = get_camera_status()
    return {
        "cameras": statuses,
        "count": len(statuses),
        "disclaimer": (
            "All depth values shown here are UNCALIBRATED VISUAL PROXIES derived "
            "from camera image classification, NOT measured water depths. "
            "The label-to-depth mapping is an expert-elicitation ASSUMPTION — see "
            "config.yaml cctv.depth_proxy_cm."
        ),
    }
