"""D7 – Task Board router."""
from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    location: str = ""
    priority: str = "medium"
    assigned_to: str = ""
    notes: str = ""
    source_type: str | None = None  # "alert" | "report" | "manual"
    source_id: int | None = None


class TaskUpdate(BaseModel):
    status: str   # open | acknowledged | in_progress | resolved
    notes: str = ""


@router.post("/tasks")
async def create_task(task: TaskCreate, db: aiosqlite.Connection = Depends(get_db)):
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """INSERT INTO tasks (title, location, priority, assigned_to, notes, source_type, source_id, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (task.title, task.location, task.priority, task.assigned_to,
         task.notes, task.source_type, task.source_id, now),
    )
    await db.commit()
    return {"id": cursor.lastrowid, "status": "open", "created_at": now}


@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, update: TaskUpdate, db: aiosqlite.Connection = Depends(get_db)):
    now = datetime.now(timezone.utc).isoformat()
    ts_fields = {
        "acknowledged": "ack_at",
        "in_progress":  "inprogress_at",
        "resolved":     "resolved_at",
    }
    ts_col = ts_fields.get(update.status)
    if ts_col:
        await db.execute(
            f"UPDATE tasks SET status=?, {ts_col}=?, notes=? WHERE id=?",
            (update.status, now, update.notes, task_id),
        )
    else:
        await db.execute(
            "UPDATE tasks SET status=?, notes=? WHERE id=?",
            (update.status, update.notes, task_id),
        )
    await db.commit()
    return {"id": task_id, "status": update.status, "updated_at": now}


@router.get("/tasks")
async def get_tasks(status: str | None = None, db: aiosqlite.Connection = Depends(get_db)):
    q = "SELECT * FROM tasks"
    params = []
    if status:
        q += " WHERE status = ?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    cursor = await db.execute(q, params)
    rows = await cursor.fetchall()
    return {"tasks": [dict(r) for r in rows], "count": len(rows)}


@router.get("/tasks/metrics")
async def task_metrics(db: aiosqlite.Connection = Depends(get_db)):
    """Compute median time-to-ack and time-to-resolve from real timestamps."""
    cursor = await db.execute(
        "SELECT created_at, ack_at, resolved_at FROM tasks WHERE ack_at IS NOT NULL OR resolved_at IS NOT NULL"
    )
    rows = await cursor.fetchall()

    ack_times = []
    res_times = []
    for row in rows:
        try:
            c = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if row["ack_at"]:
                a = datetime.fromisoformat(row["ack_at"].replace("Z", "+00:00"))
                ack_times.append((a - c).total_seconds() / 60)
            if row["resolved_at"]:
                r = datetime.fromisoformat(row["resolved_at"].replace("Z", "+00:00"))
                res_times.append((r - c).total_seconds() / 60)
        except Exception:
            pass

    def median(lst):
        if not lst:
            return None
        s = sorted(lst)
        n = len(s)
        return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 1)

    return {
        "median_ack_min": median(ack_times),
        "median_resolve_min": median(res_times),
        "sample_count": len(rows),
        "note": "Computed from real task timestamps in this demo session.",
    }
