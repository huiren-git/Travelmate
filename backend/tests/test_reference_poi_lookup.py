import pytest

from src.services import map as map_service


@pytest.mark.asyncio
async def test_fetch_poi_detail_returns_exact_named_poi_with_display_fields(monkeypatch):
    """Reference adoption needs a name-specific POI lookup instead of a generic attraction list."""

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "1",
                "pois": [
                    {"name": "故宫角楼", "address": "旁路", "location": "116.1,39.1"},
                    {
                        "name": "故宫博物院",
                        "address": "景山前街4号",
                        "location": "116.397,39.918",
                        "biz_ext": {"cost": "60"},
                        "photos": [{"url": " https://images.example.test/gugong.jpg "}],
                    },
                ],
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url, params):
            assert params["keywords"] == "故宫博物院"
            assert params["city"] == "北京"
            return Response()

    monkeypatch.setattr(map_service.settings, "amap_api_key", "test-key")
    monkeypatch.setattr(map_service.httpx, "AsyncClient", lambda **_kwargs: Client())

    poi = await map_service.fetch_poi_detail("北京", "故宫博物院")

    assert poi == {
        "name": "故宫博物院",
        "address": "景山前街4号",
        "location": "116.397,39.918",
        "price": "60",
        "image_url": "https://images.example.test/gugong.jpg",
    }
