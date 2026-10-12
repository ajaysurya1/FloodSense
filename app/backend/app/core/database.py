"""SQLite database initialization using aiosqlite."""
from __future__ import annotations

import aiosqlite
from app.core.config import settings


_initialized = False

async def get_db() -> aiosqlite.Connection:
    global _initialized
    if not _initialized:
        await init_db()
        _initialized = True
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS sensor_readings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id    TEXT NOT NULL,
                ts           TEXT NOT NULL,
                water_level_cm REAL NOT NULL,
                rainfall_mm  REAL,
                battery_pct  REAL,
                rssi         INTEGER,
                lat          REAL,
                lon          REAL,
                data_source  TEXT DEFAULT 'SIMULATED',
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sensor_devices (
                device_id    TEXT PRIMARY KEY,
                last_seen    TEXT,
                last_level   REAL,
                rate_of_rise REAL DEFAULT 0,
                battery_pct  REAL,
                rssi         INTEGER,
                lat          REAL,
                lon          REAL,
                status       TEXT DEFAULT 'offline',
                data_source  TEXT DEFAULT 'SIMULATED',
                alert_active INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS citizen_reports (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT NOT NULL,
                lat          REAL NOT NULL,
                lon          REAL NOT NULL,
                report_type  TEXT NOT NULL,
                note         TEXT,
                image_path   TEXT,
                clip_label   TEXT,
                clip_score   REAL,
                phash        TEXT,
                status       TEXT DEFAULT 'pending',
                duplicate_of INTEGER,
                dup_count    INTEGER DEFAULT 0,
                corroboration TEXT DEFAULT 'unverified',
                flags        TEXT,
                exif_ts      TEXT,
                exif_lat     REAL,
                exif_lon     REAL,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT NOT NULL,
                area         TEXT,
                ward         TEXT,
                stage        TEXT NOT NULL,
                language     TEXT,
                audience     TEXT,
                channel      TEXT,
                content_en   TEXT,
                content_ta   TEXT,
                cap_xml      TEXT,
                trigger_reason TEXT,
                data_sources TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                location     TEXT,
                priority     TEXT DEFAULT 'medium',
                status       TEXT DEFAULT 'open',
                assigned_to  TEXT,
                created_at   TEXT DEFAULT (datetime('now')),
                ack_at       TEXT,
                inprogress_at TEXT,
                resolved_at  TEXT,
                notes        TEXT,
                source_type  TEXT,
                source_id    INTEGER
            );
        """)
        await db.commit()
