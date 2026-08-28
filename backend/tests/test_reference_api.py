import pytest

from src.api.v1 import reference as reference_api
from src.core.tracing import get_trace_id, reset_trace_id, set_trace_id
from src.models.reference import AdoptReferenceRequest


@pytest.mark.asyncio
async def test_adoption_stream_creates_and_completes_a_trace(monkeypatch):
    """Protect against adopted trips calling traced map work without a trace ID."""
    previous_trace = set_trace_id(None)
    started: list[dict] = []
    ended: list[dict] = []

    async def get_reference(_reference_id):
        return {
            "id": 1,
            "destination": "北京",
            "duration": 1,
            "sequence": ["故宫"],
            "rhythm": ["2h"],
            "budget": {},
            "travelers": 2,
        }

    async def adapt_reference(*_args, **_kwargs):
        assert get_trace_id() == "trc_adopt"
        return {"draft_daily_itinerary": [{"day": 1, "items": []}]}, []

    async def validate(_state):
        return {"terminal_status": "confirmed", "is_finished": True}

    async def start_trace(**kwargs):
        started.append(kwargs)

    async def end_trace(trace_id, status, error_msg=None):
        ended.append({"trace_id": trace_id, "status": status, "error_msg": error_msg})

    monkeypatch.setattr(reference_api, "get_reference_trip", get_reference)
    monkeypatch.setattr(reference_api, "adapt_reference_trip", adapt_reference)
    monkeypatch.setattr(reference_api, "reference_validator_node", validate)
    async def increment_usage(_reference_id):
        return None

    monkeypatch.setattr(reference_api, "increment_reference_usage", increment_usage)
    monkeypatch.setattr(reference_api, "generate_trace_id", lambda: "trc_adopt", raising=False)
    monkeypatch.setattr(reference_api, "start_trace", start_trace, raising=False)
    monkeypatch.setattr(reference_api, "end_trace", end_trace, raising=False)

    try:
        response = await reference_api.adopt_reference(
            1,
            AdoptReferenceRequest(thread_id="thr_1", start_date="2026-09-01", duration=1, travelers=2),
            "user_1",
        )
        body = "".join([chunk async for chunk in response.body_iterator])
    finally:
        reset_trace_id(previous_trace)

    assert "event: done" in body
    assert started == [{"trace_id": "trc_adopt", "thread_id": "thr_1", "user_id": "user_1", "input_message": "采纳参考行程：北京"}]
    assert ended == [{"trace_id": "trc_adopt", "status": "success", "error_msg": None}]
