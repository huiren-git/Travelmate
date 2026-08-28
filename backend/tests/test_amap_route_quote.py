import pytest

from src.services import map as map_service


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, *_args, **_kwargs):
        return _Response(self.payload)

    async def post(self, *_args, **_kwargs):
        return _Response(self.payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "payload", "expected"),
    [
        (
            "metro",
            {"status": "1", "route": {"transits": [{"distance": "1500", "duration": "720", "transit_fee": "4"}]}},
            {"distance_km": 1.5, "duration_minutes": 12, "cost": 4.0},
        ),
        (
            "taxi",
            {"status": "1", "route": {"taxiCost": "16.5", "paths": [{"distance": "2100", "duration": "480"}]}},
            {"distance_km": 2.1, "duration_minutes": 8, "cost": 16.5},
        ),
        (
            "ride_hailing",
            {"status": "1", "route": {"paths": [{"distance": 2300, "duration": 540}]}},
            {"distance_km": 2.3, "duration_minutes": 9, "cost": 6.9},
        ),
    ],
)
async def test_amap_route_quote_extracts_the_mode_specific_returned_fare(monkeypatch, mode, payload, expected):
    """Breaks if a route API field is ignored in favor of local distance pricing."""
    monkeypatch.setattr(map_service.settings, "amap_api_key", "test-key")
    monkeypatch.setattr(map_service.httpx, "AsyncClient", lambda **_kwargs: _Client(payload))

    quote = await map_service.amap_route_quote("116.39,39.91", "116.40,39.92", mode, "北京")

    assert quote == expected


@pytest.mark.asyncio
async def test_amap_route_quote_does_not_log_request_url_when_the_provider_call_fails(monkeypatch, caplog):
    """Breaks if a provider exception leaks the credential-bearing request URL into logs."""

    class _FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise RuntimeError("request failed: https://example.test/route?key=secret-test-key")

    monkeypatch.setattr(map_service.settings, "amap_api_key", "test-key")
    monkeypatch.setattr(map_service.httpx, "AsyncClient", lambda **_kwargs: _FailingClient())

    assert await map_service.amap_route_quote("116.39,39.91", "116.40,39.92", "taxi") is None
    assert "secret-test-key" not in caplog.text
