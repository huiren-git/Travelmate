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

    async def enrich_costs(itinerary, _state):
        return itinerary

    class MainGraph:
        checkpointer = object()

    class AdoptionGraph:
        async def ainvoke(self, state, _config):
            return {**state, "terminal_status": "confirmed", "is_finished": True}

    async def get_graph():
        return MainGraph()

    def build_adoption_graph(checkpointer):
        assert checkpointer is MainGraph.checkpointer
        return AdoptionGraph()

    async def start_trace(**kwargs):
        started.append(kwargs)

    async def end_trace(trace_id, status, error_msg=None):
        ended.append({"trace_id": trace_id, "status": status, "error_msg": error_msg})

    monkeypatch.setattr(reference_api, "get_reference_trip", get_reference)
    monkeypatch.setattr(reference_api, "adapt_reference_trip", adapt_reference)
    monkeypatch.setattr(reference_api, "enrich_itinerary_costs", enrich_costs)
    monkeypatch.setattr(reference_api, "get_graph_async", get_graph)
    monkeypatch.setattr(reference_api, "build_reference_adoption_graph", build_adoption_graph)
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


@pytest.mark.asyncio
async def test_adoption_persists_user_scoped_enriched_state_in_checkpoint(monkeypatch):
    """A reference adoption must save the user-adjusted result, not the source case, under its new thread ID."""
    saved: dict = {}

    async def get_reference(_reference_id):
        return {"id": 1, "destination": "北京", "duration": 1, "sequence": ["故宫"], "rhythm": ["2h"], "budget": {}, "travelers": 2}

    async def adapt_reference(*_args, **_kwargs):
        return {
            "draft_daily_itinerary": [{"day": 1, "date": "2026-09-01", "items": [{"activity": "故宫", "cost": None, "image_url": "https://images.example.test/gugong.jpg"}]}],
            "draft_budget": {"total": 0, "detail": {}},
            "fetched_attractions": [],
        }, []

    async def enrich_costs(itinerary, state):
        assert state["structured_preferences"]["travelers"] == 4
        assert state["travelers"] == 4
        itinerary[0]["items"][0].update({"cost": 240.0, "cost_category": "tickets", "leg_transport_cost": 0.0})
        return itinerary

    def build_logistics(_state, _itinerary):
        return {"intercity_legs": [], "local_transport_legs": [], "accommodation": {"cost": 450.0}}

    async def enrich_transport(_legs):
        return None

    def build_budget(itinerary, logistics, level):
        assert itinerary[0]["items"][0]["cost"] == 240.0
        assert logistics["accommodation"]["cost"] == 450.0
        assert level == "mid"
        return {"level": "mid", "total": 690.0, "detail": {"tickets": 240.0, "hotel": 450.0}, "saving_tips": []}

    class MainGraph:
        checkpointer = object()

    class AdoptionGraph:
        async def ainvoke(self, state, config):
            saved["state"] = state
            saved["config"] = config
            return {
                **state,
                "daily_itinerary": state["draft_daily_itinerary"],
                "budget": state["draft_budget"],
                "draft_daily_itinerary": None,
                "draft_budget": None,
                "is_finished": True,
                "terminal_status": "confirmed",
            }

    async def get_graph():
        return MainGraph()

    def build_adoption_graph(checkpointer):
        assert checkpointer is MainGraph.checkpointer
        return AdoptionGraph()

    async def increment_usage(_reference_id):
        return None

    monkeypatch.setattr(reference_api, "get_reference_trip", get_reference)
    monkeypatch.setattr(reference_api, "adapt_reference_trip", adapt_reference)
    monkeypatch.setattr(reference_api, "enrich_itinerary_costs", enrich_costs)
    monkeypatch.setattr(reference_api, "build_travel_logistics", build_logistics)
    monkeypatch.setattr(reference_api, "enrich_local_transport_legs", enrich_transport)
    monkeypatch.setattr(reference_api, "build_reference_budget", build_budget)
    monkeypatch.setattr(reference_api, "get_graph_async", get_graph)
    monkeypatch.setattr(reference_api, "build_reference_adoption_graph", build_adoption_graph)
    monkeypatch.setattr(reference_api, "increment_reference_usage", increment_usage)
    monkeypatch.setattr(reference_api, "generate_trace_id", lambda: "trc_persist")
    async def start_trace(**_kwargs):
        return None

    async def end_trace(*_args, **_kwargs):
        return None

    monkeypatch.setattr(reference_api, "start_trace", start_trace)
    monkeypatch.setattr(reference_api, "end_trace", end_trace)

    response = await reference_api.adopt_reference(
        1,
        AdoptReferenceRequest(thread_id="adopted_1", start_date="2026-09-01", duration=1, travelers=4),
        "user_1",
    )
    body = "".join([chunk async for chunk in response.body_iterator])

    assert saved["config"] == {"configurable": {"thread_id": "adopted_1"}}
    assert saved["state"]["draft_daily_itinerary"][0]["items"][0]["cost"] == 240.0
    assert saved["state"]["draft_budget"]["total"] == 690.0
    assert "event: done" in body
