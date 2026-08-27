"""Dedicated SQLite storage for reusable reference-trip blueprints."""

from pathlib import Path
from typing import Optional

import aiosqlite

from src.config.settings import settings


REFERENCE_DB_PATH = Path(settings.database_dir) / "reference.db"
_reference_db_pool: Optional[aiosqlite.Connection] = None


async def get_reference_db_connection() -> aiosqlite.Connection:
    global _reference_db_pool
    if _reference_db_pool is None:
        REFERENCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _reference_db_pool = await aiosqlite.connect(str(REFERENCE_DB_PATH), isolation_level=None)
        await _reference_db_pool.execute("PRAGMA foreign_keys = ON")
        await _reference_db_pool.execute("PRAGMA journal_mode = WAL")
        await init_reference_tables(_reference_db_pool)
    return _reference_db_pool


async def init_reference_tables(conn: Optional[aiosqlite.Connection] = None) -> None:
    connection = conn or await get_reference_db_connection()
    await connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_trace_id TEXT,
            destination TEXT NOT NULL,
            duration INTEGER NOT NULL,
            sequence TEXT NOT NULL,
            sequence_hash TEXT NOT NULL,
            rhythm TEXT,
            budget TEXT,
            travelers INTEGER,
            tags TEXT,
            experience_tips TEXT,
            score INTEGER,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(destination, duration, sequence_hash)
        )
        """
    )
    async with connection.execute("PRAGMA table_info(reference_trips)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
    if "travelers" not in columns:
        await connection.execute("ALTER TABLE reference_trips ADD COLUMN travelers INTEGER")


async def close_reference_db_pool() -> None:
    global _reference_db_pool
    if _reference_db_pool is not None:
        await _reference_db_pool.close()
        _reference_db_pool = None
