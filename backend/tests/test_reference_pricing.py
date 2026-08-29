import pytest

from src.agents import cost_enrich


@pytest.mark.asyncio
async def test_enriched_costs_mark_amap_free_and_rule_sources(monkeypatch):
    """UI labels depend on whether an item price was returned, confirmed free, or estimated."""

    async def no_food(_city):
        return []

    async def no_distance(*_args):
        return None

    monkeypatch.setattr(cost_enrich, "fetch_food_pois_with_cache", no_food)
    monkeypatch.setattr(cost_enrich, "amap_distance_km", no_distance)
    itinerary = [{"items": [
        {"activity": "故宫", "poi_ref": "故宫", "location": "116.397,39.918"},
        {"activity": "免费公园", "poi_ref": "免费公园", "location": "116.398,39.919"},
        {"activity": "未知景点"},
    ]}]
    state = {
        "destination": "北京",
        "structured_preferences": {"travelers": 2, "budget_level": "mid"},
        "fetched_attractions": [
            {"name": "故宫", "price": "60", "location": "116.397,39.918"},
            {"name": "免费公园", "price": "0", "location": "116.398,39.919"},
        ],
    }

    result = await cost_enrich.enrich_itinerary_costs(itinerary, state)

    assert result[0]["items"][0]["estimate_source"] == "amap"
    assert result[0]["items"][1]["estimate_source"] == "free"
    assert result[0]["items"][2]["estimate_source"] == "rule"
