"""
CLIP-based image classifier for citizen reports (D4).
Loads openai/clip-vit-base-patch32 once at startup.
Falls back to 'needs_manual_review' if model is unavailable.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None
_processor = None
_READY = False
_LABELS = [
    "a flooded street",
    "a waterlogged road",
    "a blocked storm drain with water",
    "a dry road",
    "an indoor photo",
    "a screenshot",
    "a clear sunny day",
]


async def warm_up() -> None:
    """Pre-load CLIP model (non-blocking, runs at startup)."""
    global _model, _processor, _READY
    try:
        from transformers import CLIPProcessor, CLIPModel
        import torch
        logger.info("Loading CLIP model (openai/clip-vit-base-patch32)…")
        loop = asyncio.get_event_loop()
        _processor, _model = await loop.run_in_executor(None, _load_clip)
        _READY = True
        logger.info("CLIP model ready.")
    except Exception as e:
        logger.warning(f"CLIP model unavailable: {e}. Will flag reports for manual review.")


def _load_clip():
    from transformers import CLIPProcessor, CLIPModel
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    mdl  = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    mdl.eval()
    return proc, mdl


async def classify(image_bytes: bytes) -> dict:
    """
    Returns {label: str, score: float, source: 'CLIP'|'manual_review'}.
    Score is a softmax probability — not a calibrated confidence.
    """
    if not _READY or _model is None:
        return {"label": "needs_manual_review", "score": 0.0, "source": "manual_review"}

    try:
        import torch
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_clip, img)
        return result
    except Exception as e:
        logger.error(f"CLIP inference error: {e}")
        return {"label": "needs_manual_review", "score": 0.0, "source": "manual_review"}


def _run_clip(img) -> dict:
    import torch
    inputs = _processor(text=_LABELS, images=img, return_tensors="pt", padding=True)
    with torch.no_grad():
        outputs = _model(**inputs)
        logits = outputs.logits_per_image[0]
        probs  = logits.softmax(dim=0).tolist()
    best_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
    return {
        "label": _LABELS[best_idx],
        "score": round(probs[best_idx], 4),
        "all_labels": [{"label": l, "score": round(s, 4)} for l, s in zip(_LABELS, probs)],
        "source": "CLIP",
    }


def is_suspicious(label: str, score: float) -> bool:
    """Flag reports that are likely not real flood photos."""
    suspicious_labels = {"a dry road", "an indoor photo", "a screenshot", "a clear sunny day"}
    return label in suspicious_labels or score < 0.30
