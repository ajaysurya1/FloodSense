"""D1 – Risk router."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.risk.engine import compute_risk

router = APIRouter()


@router.get("/risk")
async def get_risk(
    horizon: int = Query(60, description="Forecast horizon in minutes (30, 60, 120, 180)")
):
    """
    Returns GeoJSON FeatureCollection of risk cells.

    ⚠️ All scores are **heuristic, uncalibrated estimates**.
    Complements NDMA SACHET; does not replace official warnings.
    """
    data = await compute_risk(horizon_min=horizon)
    return JSONResponse(content=data)
