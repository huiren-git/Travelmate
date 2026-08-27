import pytest

from src.services import reference_db
from src.services import reference_trip_service as service


def _confirmed_state(score: int = 85, destination: str = "北京") -> dict:
    return {
        "destination": destination,
        "duration": 2,
        "daily_itinerary": [
            {"day": 1, "items": [{"activity": "故宫", "duration": "3h"}]},
            {"day": 2, "items": [{"activity": "景山", "duration": "1h"}]},
        ],
        "budget": {"total": 2800, "detail": {"hotel": 1200}},
        "structured_preferences": {"interests": ["历史人文"], "pace": "relaxed"},
        "validation_report": {
            "score": score,
            "warnings": ["周一部分场馆闭馆"],
            "suggestions": ["提前预约", "周一部分场馆闭馆"],
        },
        "is_finished": True,
        "terminal_status": "confirmed",
    }


@pytest.mark.asyncio
async def test_archive_reference_trip_is_eligible_idempotent_and_queryable(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_db, "REFERENCE_DB_PATH", tmp_path / "reference.db")
    await reference_db.close_reference_db_pool()

    assert await service.archive_reference_trip(_confirmed_state(), "trc_1") is True
    assert await service.archive_reference_trip(_confirmed_state(), "trc_2") is False

    rows, total = await service.list_reference_trips(page=1, page_size=20)
    assert total == 1
    assert rows[0]["destination"] == "北京"
    assert rows[0]["sequence"] == ["故宫", "景山"]
    assert rows[0]["rhythm"] == ["3h", "1h"]
    assert rows[0]["experience_tips"] == "周一部分场馆闭馆；提前预约"

    await reference_db.close_reference_db_pool()


@pytest.mark.asyncio
async def test_archive_reference_trip_rejects_non_confirmed_or_low_score(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_db, "REFERENCE_DB_PATH", tmp_path / "reference.db")
    await reference_db.close_reference_db_pool()

    low_score = _confirmed_state(score=84)
    failed = _confirmed_state()
    failed["terminal_status"] = "failed"
    assert await service.archive_reference_trip(low_score, "trc_low") is False
    assert await service.archive_reference_trip(failed, "trc_failed") is False

    rows, total = await service.list_reference_trips(page=1, page_size=20)
    assert rows == []
    assert total == 0
    await reference_db.close_reference_db_pool()
