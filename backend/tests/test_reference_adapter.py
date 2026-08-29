import pytest

from src.services import reference_adapter


@pytest.mark.asyncio
async def test_adapt_reference_trip_retains_resolved_poi_details(monkeypatch):
    """A resolved POI must survive adaptation so downstream pricing and UI do not see blank fields."""

    async def weather(_city):
        return {"desc": "晴"}

    async def poi(_city, _activity):
        return {
            "name": "故宫博物院",
            "address": "北京市东城区景山前街4号",
            "location": "116.397,39.918",
            "image_url": "https://images.example.test/gugong.jpg",
            "price": "60",
        }

    monkeypatch.setattr(reference_adapter, "fetch_weather_with_cache", weather)
    monkeypatch.setattr(reference_adapter, "find_poi", poi)

    draft, _ = await reference_adapter.adapt_reference_trip(
        {
            "destination": "北京",
            "duration": 1,
            "sequence": ["故宫"],
            "rhythm": ["3h"],
            "travelers": 2,
        },
        duration=1,
        start_date="2026-09-01",
        travelers=4,
    )

    item = draft["draft_daily_itinerary"][0]["items"][0]
    assert item["activity"] == "故宫博物院"
    assert item["address"] == "北京市东城区景山前街4号"
    assert item["location"] == "116.397,39.918"
    assert item["image_url"] == "https://images.example.test/gugong.jpg"
    assert item["poi_ref"] == "故宫博物院"
    assert draft["fetched_attractions"] == [{
        "name": "故宫博物院",
        "address": "北京市东城区景山前街4号",
        "location": "116.397,39.918",
        "image_url": "https://images.example.test/gugong.jpg",
        "price": "60",
    }]


def test_build_reference_budget_uses_enriched_item_costs_and_logistics():
    """The adopted budget must be derived from the user's enriched itinerary rather than the source-case total."""
    budget = reference_adapter.build_reference_budget(
        [{"items": [
            {"cost": 240.0, "cost_category": "tickets"},
            {"cost": 120.0, "cost_category": "food"},
        ]}],
        {
            "intercity_legs": [{"cost": 300.0}],
            "local_transport_legs": [{"cost": 12.0}],
            "accommodation": {"cost": 450.0},
        },
        "mid",
    )

    assert budget == {
        "level": "mid",
        "total": 1122.0,
        "detail": {
            "food": 120.0,
            "tickets": 240.0,
            "intercity_transport": 300.0,
            "local_transport": 12.0,
            "hotel": 450.0,
        },
        "saving_tips": [],
    }
