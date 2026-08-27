"""Archive and retrieve date-free reference itinerary blueprints."""

import hashlib
import json
from typing import Any, Mapping, Optional

from src.services.reference_db import get_reference_db_connection
from src.utils.state_utils import get_travelers


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _tips(report: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in ("warnings", "suggestions"):
        for value in report.get(key) or []:
            text = str(value).strip()
            if text and text not in values:
                values.append(text)
    return "；".join(values)


def _tags(preferences: Mapping[str, Any], budget: Mapping[str, Any]) -> list[str]:
    tags = [str(item).strip() for item in preferences.get("interests") or [] if str(item).strip()]
    pace = str(preferences.get("pace") or "").strip()
    if pace:
        tags.append({"relaxed": "轻松", "moderate": "适中", "compact": "紧凑"}.get(pace, pace))
    level = str(budget.get("level") or "").strip()
    if level:
        tags.append({"economy": "经济", "mid": "中等预算", "luxury": "高预算"}.get(level, level))
    return list(dict.fromkeys(tags))


async def archive_reference_trip(state: Mapping[str, Any], source_trace_id: Optional[str] = None) -> bool:
    report = state.get("validation_report") or {}
    if not (state.get("is_finished") and state.get("terminal_status") == "confirmed" and int(report.get("score") or 0) >= 85):
        return False
    destination = str(state.get("destination") or "").strip()
    duration = state.get("duration")
    itinerary = state.get("daily_itinerary") or []
    if not destination or not isinstance(duration, int) or duration <= 0:
        return False
    items = [item for day in itinerary for item in (day.get("items") or [])]
    sequence = [str(item.get("activity") or "").strip() for item in items if str(item.get("activity") or "").strip()]
    rhythm = [str(item.get("duration") or "").strip() for item in items]
    if not sequence:
        return False
    sequence_hash = hashlib.sha256(_json(sequence).encode("utf-8")).hexdigest()
    budget = dict(state.get("budget") or {})
    preferences = state.get("structured_preferences") or {}
    travelers = get_travelers(state)
    conn = await get_reference_db_connection()
    cursor = await conn.execute(
        """INSERT INTO reference_trips
           (source_trace_id, destination, duration, sequence, sequence_hash, rhythm, budget, travelers, tags, experience_tips, score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(destination, duration, sequence_hash) DO NOTHING""",
        (source_trace_id, destination, duration, _json(sequence), sequence_hash, _json(rhythm), _json(budget), travelers, _json(_tags(preferences, budget)), _tips(report), int(report["score"])),
    )
    return cursor.rowcount == 1


def _row(row: tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
    value = dict(zip(columns, row))
    for key in ("sequence", "rhythm", "budget", "tags"):
        value[key] = json.loads(value[key]) if value.get(key) else ([] if key in {"sequence", "rhythm", "tags"} else {})
    return value


async def list_reference_trips(page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    conn = await get_reference_db_connection()
    async with conn.execute("SELECT COUNT(*) FROM reference_trips") as cursor:
        total = int((await cursor.fetchone())[0])
    offset = (page - 1) * page_size
    async with conn.execute("SELECT * FROM reference_trips ORDER BY score DESC, usage_count DESC, created_at DESC LIMIT ? OFFSET ?", (page_size, offset)) as cursor:
        columns = [item[0] for item in cursor.description]
        return [_row(row, columns) for row in await cursor.fetchall()], total


async def get_reference_trip(reference_id: int) -> Optional[dict[str, Any]]:
    conn = await get_reference_db_connection()
    async with conn.execute("SELECT * FROM reference_trips WHERE id = ?", (reference_id,)) as cursor:
        row = await cursor.fetchone()
        return _row(row, [item[0] for item in cursor.description]) if row else None


async def increment_reference_usage(reference_id: int) -> None:
    conn = await get_reference_db_connection()
    await conn.execute("UPDATE reference_trips SET usage_count = usage_count + 1 WHERE id = ?", (reference_id,))
