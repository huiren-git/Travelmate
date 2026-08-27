import pytest

from src.services import reference_adapter as adapter


@pytest.mark.asyncio
async def test_adapter_compresses_days_scales_budget_and_records_log(monkeypatch):
    async def clear_weather(_city):
        return {"city": "北京", "desc": "晴", "date": "2026-10-01"}

    monkeypatch.setattr(adapter, "fetch_weather_with_cache", clear_weather)
    reference = {
        "destination": "北京", "duration": 3,
        "sequence": ["故宫", "景山", "颐和园"], "rhythm": ["3h", "1h", "4h"],
        "budget": {"total": 2800, "detail": {"hotel": 1200}}, "travelers": 2,
    }
    state, log = await adapter.adapt_reference_trip(reference, duration=2, start_date="2026-10-01", travelers=1)
    assert len(state["draft_daily_itinerary"]) == 2
    assert state["draft_budget"]["total"] == 1400.0
    assert {entry["kind"] for entry in log} == {"duration_compressed", "budget_scaled"}


@pytest.mark.asyncio
async def test_adapter_scales_budget_from_reference_travelers_not_budget_metadata(monkeypatch):
    async def clear_weather(_city):
        return {"city": "北京", "desc": "晴", "date": "2026-10-01"}

    monkeypatch.setattr(adapter, "fetch_weather_with_cache", clear_weather)
    reference = {
        "destination": "北京", "duration": 1, "sequence": ["故宫"], "rhythm": ["3h"],
        "budget": {"total": 2800, "travelers": 99}, "travelers": 2,
    }
    state, log = await adapter.adapt_reference_trip(reference, duration=1, start_date="2026-10-01", travelers=1)
    assert state["draft_budget"]["total"] == 1400.0
    assert log[-1]["from"] == 2


@pytest.mark.asyncio
async def test_adapter_replaces_closed_and_rainy_outdoor_pois(monkeypatch):
    async def storm(_city): return {"city": "北京", "desc": "暴雨", "date": "2026-10-01"}
    async def poi(_city, name): return {"name": name, "business": "已关闭"} if name == "故宫" else {"name": name, "business": "营业中"}
    async def replacement(_city, _name, indoor): return {"name": "国家博物馆" if indoor else "北海公园"}
    monkeypatch.setattr(adapter, "fetch_weather_with_cache", storm)
    monkeypatch.setattr(adapter, "find_poi", poi)
    monkeypatch.setattr(adapter, "find_replacement_poi", replacement)
    state, log = await adapter.adapt_reference_trip({"destination":"北京","duration":1,"sequence":["故宫"],"rhythm":["3h"],"budget":{}}, duration=1, start_date="2026-10-01", travelers=1)
    assert state["draft_daily_itinerary"][0]["items"][0]["activity"] == "国家博物馆"
    assert {entry["kind"] for entry in log} >= {"closed_replaced", "weather_replaced"}
