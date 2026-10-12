"""
FloodSense backend – main FastAPI application entry point.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.routers import risk, sensors, reports, alerts, tasks, dashboard
from app.routers import cctv as cctv_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown tasks."""
    await init_db()
    # Pre-warm CLIP model in background (non-blocking – fails gracefully)
    from app.services import clip_classifier
    asyncio.create_task(clip_classifier.warm_up())

    # Start CCTV ingest loop in background (non-blocking)
    from app.services import cctv_ingest
    asyncio.create_task(cctv_ingest.start_ingest_loop())

    yield
    # teardown if needed


app = FastAPI(
    title="FloodSense API",
    description=(
        "Hyperlocal Flood Early-Warning System API.\n\n"
        "WARNING: ALL risk outputs are **heuristic, uncalibrated estimates** and do NOT guarantee "
        "flood occurrence. Every data source is tagged LIVE, SIMULATED, SEED, or CCTV.\n"
        "Alerts complement and do not replace official NDMA SACHET warnings."
    ),
    version="0.2.0-hackathon",
    lifespan=lifespan,
)

# ── CORS (allow Vite dev server) ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(risk.router, prefix="/api", tags=["risk"])
app.include_router(sensors.router, prefix="/api", tags=["sensors"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(cctv_router.router, prefix="/api", tags=["cctv"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mode": settings.mode,
        "version": "0.2.0-hackathon",
        "disclaimer": (
            "All risk outputs are heuristic, uncalibrated estimates. "
            "Complements NDMA SACHET; does not replace official warnings."
        ),
    }


@app.get("/api/config/wards")
async def list_wards():
    """Return all available ward configurations."""
    wards_path = Path(settings.data_dir) / "wards.json"
    if wards_path.exists():
        with open(wards_path, encoding="utf-8") as f:
            return json.load(f)
    # Legacy fallback
    ward_path = Path(settings.data_dir) / "ward.json"
    with open(ward_path, encoding="utf-8") as f:
        ward = json.load(f)
    if "ward_id" not in ward:
        ward["ward_id"] = "kotturpuram"
    return [ward]


@app.get("/api/config/ward/{ward_id}")
async def get_ward(ward_id: str):
    """Return configuration for a specific ward."""
    wards = await list_wards()
    for w in wards:
        if w.get("ward_id") == ward_id:
            return w
    raise HTTPException(status_code=404, detail=f"Ward '{ward_id}' not found")


@app.get("/api/config/ward")
async def ward_config():
    """Return the first (default) ward configuration. Kept for backward compatibility."""
    wards = await list_wards()
    return wards[0]


@app.get("/api/config/mode")
async def get_mode():
    return {"mode": settings.mode}
