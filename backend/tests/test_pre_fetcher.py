import re
import sys
from pathlib import Path

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


CITY = "北京"
START_DATE = "2026-08-10"
ATTRACTION_LIMIT = 10


def _require_key(value: str, name: str) -> None:
    if not value:
        pytest.skip(f"{name} is required for real API integration tests")


async def _fetch_raw_qweather(city: str) -> dict:
    from src.config.settings import settings

    _require_key(settings.qweather_api_key, "QWEATHER_API_KEY")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://devapi.qweather.com/v7/weather/now",
            params={"location": city, "key": settings.qweather_api_key},
        )
        response.raise_for_status()
        return response.json()


async def _fetch_raw_amap(city: str, limit: int = ATTRACTION_LIMIT) -> dict:
    from src.config.settings import settings

    _require_key(settings.amap_api_key, "AMAP_API_KEY")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            "https://restapi.amap.com/v3/place/text",
            params={
                "keywords": "景点",
                "city": city,
                "citylimit": "true",
                "offset": limit,
                "page": 1,
                "extensions": "all",
                "key": settings.amap_api_key,
            },
        )
        response.raise_for_status()
        return response.json()


def _assert_weather_service_shape(weather_info: dict) -> None:
    assert set(weather_info) == {"city", "temp", "desc", "humidity", "wind", "date"}
    assert isinstance(weather_info["city"], str)
    assert isinstance(weather_info["temp"], float)
    assert isinstance(weather_info["desc"], str)
    assert isinstance(weather_info["humidity"], float)
    assert isinstance(weather_info["wind"], str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", weather_info["date"])


def _assert_attraction_service_shape(attraction: dict) -> None:
    assert set(attraction) == {"name", "address", "location", "rating", "price"}
    assert isinstance(attraction["name"], str)
    assert "location" in attraction
    assert "rating" in attraction
    assert "price" in attraction


@pytest.mark.asyncio
async def test_fetch_weather_with_real_api_matches_qweather_format():
    from src.services.weather import fetch_weather_with_cache

    raw = await _fetch_raw_qweather(CITY)
    assert raw.get("code") == "200", f"QWeather API returned unexpected response: {raw}"
    assert isinstance(raw.get("now"), dict)

    raw_now = raw["now"]
    for field in ("temp", "text", "humidity", "windDir", "windScale"):
        assert field in raw_now

    weather_info = await fetch_weather_with_cache(CITY, redis=None)

    _assert_weather_service_shape(weather_info)
    assert weather_info["city"] == CITY
    assert weather_info["desc"] == raw_now["text"]
    assert weather_info["temp"] == float(raw_now["temp"])
    assert weather_info["humidity"] == float(raw_now["humidity"])
    assert weather_info["wind"] == raw_now.get("windDir", "") + raw_now.get("windScale", "")


@pytest.mark.asyncio
async def test_fetch_attractions_with_real_api_matches_amap_format():
    from src.services.map import fetch_attractions_with_cache

    raw = await _fetch_raw_amap(CITY)
    assert raw.get("status") == "1", f"AMap API returned unexpected response: {raw}"
    assert isinstance(raw.get("pois"), list)
    assert raw["pois"], "AMap API returned no POIs for 北京"

    attractions = await fetch_attractions_with_cache(CITY, redis=None, limit=ATTRACTION_LIMIT)

    assert attractions, "Service returned no attractions for 北京"
    assert len(attractions) <= ATTRACTION_LIMIT
    _assert_attraction_service_shape(attractions[0])

    raw_pois_by_name = {poi.get("name"): poi for poi in raw["pois"] if poi.get("name")}
    service_first = attractions[0]
    assert service_first["name"] in raw_pois_by_name

    raw_first = raw_pois_by_name[service_first["name"]]
    raw_biz_ext = raw_first.get("biz_ext") or {}
    if not isinstance(raw_biz_ext, dict):
        raw_biz_ext = {}

    assert service_first["address"] == raw_first.get("address", "")
    assert service_first["location"] == raw_first.get("location", "")
    assert service_first["rating"] == raw_biz_ext.get("rating")
    assert service_first["price"] == raw_biz_ext.get("cost")


@pytest.mark.asyncio
async def test_pre_fetcher_node_fetches_beijing_weather_and_attractions_with_real_api(monkeypatch):
    from src.graph.pre_fetcher import pre_fetcher_node
    import src.services.redis_client as redis_service

    monkeypatch.setattr(redis_service, "redis_client", None)

    result = await pre_fetcher_node(
        {
            "destination": CITY,
            "start_date": START_DATE,
        }
    )

    assert set(result) == {"weather_info", "fetched_attractions"}

    weather_info = result["weather_info"]
    attractions = result["fetched_attractions"]

    _assert_weather_service_shape(weather_info)
    assert weather_info["city"] == CITY
    assert weather_info["date"] == START_DATE
    assert weather_info["desc"] != "未知（API调用失败）"

    assert isinstance(attractions, list)
    assert attractions, "pre_fetcher_node returned no attractions for 北京"
    assert len(attractions) <= ATTRACTION_LIMIT
    _assert_attraction_service_shape(attractions[0])
