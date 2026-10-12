"""D1 – Risk router."""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.risk.engine import compute_risk

router = APIRouter()


@router.get("/risk")
async def get_risk(
    horizon: int = Query(60, description="Forecast horizon in minutes (30, 60, 120, 180)"),
    ward_id: str | None = Query(None, description="Ward slug; defaults to first ward if omitted"),
):
    """
    Returns GeoJSON FeatureCollection of risk cells for the given ward.

    WARNING: All scores are **heuristic, uncalibrated estimates**.
    Complements NDMA SACHET; does not replace official warnings.
    """
    data = await compute_risk(horizon_min=horizon, ward_id=ward_id)
    return JSONResponse(content=data)
