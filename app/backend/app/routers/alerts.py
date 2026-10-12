"""D6 – Staged Neighbourhood Alerts router."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from xml.etree import ElementTree as ET

import aiosqlite
import yaml
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()

_templates: dict | None = None


def _load_templates() -> dict:
    global _templates
    if _templates is None:
        with open(settings.template_file, encoding="utf-8") as f:
            _templates = yaml.safe_load(f)
    return _templates


def _safe_format(template: str, **kwargs) -> str:
    """Format template, replacing missing keys with [FILL IN]."""
    class SafeDict(dict):
        def __missing__(self, key):
            return f"[FILL IN: {key}]"
    return Formatter().vformat(template, [], SafeDict(**kwargs))


def _generate_cap_xml(alert: dict) -> str:
    """Generate CAP 1.2 XML stub. Labelled 'format demo, not transmitted to SACHET'."""
    root = ET.Element("alert", xmlns="urn:oasis:names:tc:emergency:cap:1.2")
    ET.SubElement(root, "identifier").text = f"floodsense-{alert['id']}"
    ET.SubElement(root, "sender").text = "FloodSense-Demo@hackathon.local"
    ET.SubElement(root, "sent").text = alert["ts"]
    ET.SubElement(root, "status").text = "Test"
    ET.SubElement(root, "msgType").text = "Alert"
    ET.SubElement(root, "scope").text = "Public"
    ET.SubElement(root, "note").text = (
        "FORMAT DEMO – not transmitted to SACHET. "
        "Heuristic estimate only. Complements NDMA SACHET official warnings."
    )
    info = ET.SubElement(root, "info")
    ET.SubElement(info, "language").text = "en-IN"
    ET.SubElement(info, "category").text = "Met"
    ET.SubElement(info, "event").text = f"Flood {alert['stage']}"
    ET.SubElement(info, "urgency").text = "Immediate" if alert["stage"] == "URGENT" else "Expected"
    ET.SubElement(info, "severity").text = alert["stage"]
    ET.SubElement(info, "certainty").text = "Likely"
    ET.SubElement(info, "headline").text = f"Flood {alert['stage']} – {alert.get('area', 'Demo Ward')}"
    ET.SubElement(info, "description").text = alert.get("content_en", "")
    return ET.tostring(root, encoding="unicode")


class AlertRequest(BaseModel):
    area: str = "Demo Ward"
    stage: str = "WATCH"  # WATCH | WARNING | URGENT
    onset_window: str = "45–90 min"
    confidence: str = "Medium"
    reasons: list[str] = []
    drain_name: str = "Main Road Storm Drain"
    street: str = "Kotturpuram Main Road"
    shelter_name: str = "MRTS Evacuation Point"
    trigger_reason: str = ""
    data_sources: str = "Open-Meteo (LIVE), terrain (SEED), hotspots (SEED)"
    languages: list[str] = ["en", "ta"]
    audiences: list[str] = ["resident", "official"]
    channels: list[str] = ["SMS", "WhatsApp"]


@router.post("/alerts/generate")
async def generate_alert(req: AlertRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Generate staged alert messages for resident and official audiences."""
    import json as _json
    with open(Path(settings.data_dir) / "ward.json", encoding="utf-8") as f:
        ward = _json.load(f)

    stage_key = req.stage.lower()
    templates = _load_templates()["alert"]

    now = datetime.now(timezone.utc).isoformat()
    hours_map = {"watch": "2–3", "warning": "1–2", "urgent": "< 1"}
    hours = hours_map.get(stage_key, "unknown")
    reasons_str = "; ".join(req.reasons) if req.reasons else "Multiple risk factors"

    fmt_kwargs = dict(
        area=req.area,
        ward=ward["name"],
        hours=hours,
        onset_window=req.onset_window,
        confidence=req.confidence,
        reasons=reasons_str,
        drain_name=req.drain_name,
        street=req.street,
        shelter_name=req.shelter_name,
        trigger_reason=req.trigger_reason,
        data_sources=req.data_sources,
        timestamp=now,
    )

    alert_rows = []
    for lang in req.languages:
        for audience in req.audiences:
            try:
                tmpl = templates[stage_key][audience][lang]
                content = _safe_format(tmpl, **fmt_kwargs)
            except (KeyError, TypeError):
                content = f"[Template missing for {stage_key}/{audience}/{lang}]"

            cursor = await db.execute(
                """INSERT INTO alerts (ts, area, ward, stage, language, audience, channel, content_en, content_ta, trigger_reason, data_sources)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (now, req.area, ward["name"], req.stage.upper(), lang,
                 audience, ",".join(req.channels),
                 content if lang == "en" else "",
                 content if lang == "ta" else "",
                 req.trigger_reason, req.data_sources),
            )
            await db.commit()
            alert_id = cursor.lastrowid

            # CAP XML (en official only)
            cap_xml = None
            if lang == "en" and audience == "official":
                cap_xml = _generate_cap_xml({
                    "id": alert_id, "ts": now, "stage": req.stage.upper(),
                    "area": req.area, "content_en": content,
                })

            alert_rows.append({
                "id": alert_id,
                "ts": now,
                "stage": req.stage.upper(),
                "area": req.area,
                "ward": ward["name"],
                "language": lang,
                "audience": audience,
                "channels": req.channels,
                "content": content,
                "cap_xml": cap_xml,
                "footer": "Complements official NDMA SACHET warnings; follow government-authorised alerts.",
                "tamil_note": (
                    "Tamil copy needs review by a native speaker before any real use."
                    if lang == "ta" else None
                ),
            })

    return {"alerts": alert_rows, "count": len(alert_rows)}


@router.get("/alerts")
async def get_alerts(limit: int = 50, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    return {"alerts": [dict(r) for r in rows], "count": len(rows)}
