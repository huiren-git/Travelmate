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


async def _fetch_raw_qweather(latitude: float, longitude: float) -> dict:
    from src.config.settings import settings

    _require_key(settings.qweather_api_key, "QWEATHER_API_KEY")
    _require_key(settings.qweather_api_host, "QWEATHER_API_HOST")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://{settings.qweather_api_host}/weather/v1/current/{latitude:.2f}/{longitude:.2f}",
            headers={"X-QW-Api-Key": settings.qweather_api_key},
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
    assert set(attraction) == {"name", "address", "location", "rating", "price", "image_url"}
    assert isinstance(attraction["name"], str)
    assert "location" in attraction
    assert "rating" in attraction
    assert "price" in attraction
    assert "image_url" in attraction


def test_first_photo_url_uses_first_amap_photo_url():
    from src.services.map import _first_photo_url

    assert _first_photo_url({"photos": [{"url": " https://example.com/photo.jpg "}]}) == "https://example.com/photo.jpg"


@pytest.mark.asyncio
async def test_geocode_city_returns_latitude_and_longitude(monkeypatch):
    from src.services import map as map_service

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "1", "geocodes": [{"location": "116.41,39.92"}]}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params):
            captured.update(url=url, params=params)
            return FakeResponse()

    monkeypatch.setattr(map_service.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(map_service.settings, "amap_api_key", "test-key")

    assert await map_service.geocode_city("北京") == (39.92, 116.41)
    assert captured["url"] == "https://restapi.amap.com/v3/geocode/geo"
    assert captured["params"]["address"] == "北京"


@pytest.mark.asyncio
async def test_fetch_weather_uses_configured_host_and_api_key_header(monkeypatch):
    from src.services import weather as weather_service

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "temperature": {"value": 28},
                "condition": {"text": "晴"},
                "humidity": 0.5,
                "wind": {"direction": {"compass": "n"}, "scale": 3},
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            captured.update(url=url, headers=headers)
            return FakeResponse()

    monkeypatch.setattr(weather_service.httpx, "AsyncClient", FakeAsyncClient)
    async def fake_geocode_city(city):
        assert city == "北京"
        return 39.92, 116.41

    monkeypatch.setattr(weather_service, "geocode_city", fake_geocode_city)
    monkeypatch.setattr(weather_service.settings, "qweather_api_host", "abcxyz.qweatherapi.com", raising=False)
    monkeypatch.setattr(weather_service.settings, "qweather_api_key", "test-key")

    weather_info = await weather_service.fetch_weather_with_cache("北京")

    assert weather_info["desc"] == "晴"
    assert captured["url"] == "https://abcxyz.qweatherapi.com/weather/v1/current/39.92/116.41"
    assert captured["headers"] == {"X-QW-Api-Key": "test-key"}


@pytest.mark.asyncio
async def test_fetch_activity_image_url_queries_destination_and_activity(monkeypatch):
    from src.services import map as map_service

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "1",
                "pois": [
                    {
                        "name": "北海公园",
                        "photos": [{"url": " https://amap.example.com/beihai.jpg "}],
                    }
                ],
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr(map_service.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(map_service.settings, "amap_api_key", "test-key")

    image_url = await map_service.fetch_activity_image_url("北京", "北海公园")

    assert image_url == "https://amap.example.com/beihai.jpg"
    assert captured["params"]["keywords"] == "北京 北海公园"
    assert captured["params"]["city"] == "北京"
    assert captured["params"]["offset"] == 1


@pytest.mark.asyncio
async def test_fetch_weather_with_real_api_matches_qweather_format():
    from src.services.weather import fetch_weather_with_cache

    weather_info = await fetch_weather_with_cache(CITY, redis=None)

    _assert_weather_service_shape(weather_info)
    assert weather_info["city"] == CITY
    assert weather_info["desc"] != "未知（API调用失败）"


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
    raw_photos = raw_first.get("photos")
    expected_image_url = ""
    if isinstance(raw_photos, list) and raw_photos:
        first_photo = raw_photos[0]
        if isinstance(first_photo, dict) and isinstance(first_photo.get("url"), str):
            expected_image_url = first_photo["url"].strip()
    assert service_first["image_url"] == expected_image_url


@pytest.mark.asyncio
async def test_pre_fetcher_node_fetches_beijing_weather_and_attractions_with_real_api(monkeypatch):
    from src.graph.pre_fetcher import pre_fetcher_node
    from src.config.settings import settings
    import src.services.redis_client as redis_service

    _require_key(settings.qweather_api_key, "QWEATHER_API_KEY")
    _require_key(settings.qweather_api_host, "QWEATHER_API_HOST")
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
