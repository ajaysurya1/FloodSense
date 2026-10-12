"""
FloodSense backend – main FastAPI application entry point.
"""
from __future__ import annotations

import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.routers import risk, sensors, reports, alerts, tasks, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown tasks."""
    await init_db()
    # Pre-warm CLIP model in background (non-blocking – fails gracefully)
    from app.services import clip_classifier
    asyncio.create_task(clip_classifier.warm_up())
    yield
    # teardown if needed


app = FastAPI(
    title="FloodSense API",
    description=(
        "Hyperlocal Flood Early-Warning System API.\n\n"
        "⚠️ ALL risk outputs are **heuristic, uncalibrated estimates** and do NOT guarantee "
        "flood occurrence. Every data source is tagged LIVE, SIMULATED, or SEED.\n"
        "Alerts complement—and do not replace—official NDMA SACHET warnings."
    ),
    version="0.1.0-hackathon",
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


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "mode": settings.mode,
        "version": "0.1.0-hackathon",
        "disclaimer": (
            "All risk outputs are heuristic, uncalibrated estimates. "
            "Complements NDMA SACHET; does not replace official warnings."
        ),
    }


@app.get("/api/config/ward")
async def ward_config():
    """Return the active ward configuration."""
    import json
    ward_path = Path(settings.data_dir) / "ward.json"
    with open(ward_path) as f:
        return json.load(f)


@app.get("/api/config/mode")
async def get_mode():
    return {"mode": settings.mode}
