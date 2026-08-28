from src.services.travel_logistics import build_travel_logistics
import pytest


def test_missing_origin_creates_pending_intercity_leg_excluded_from_budget():
    logistics = build_travel_logistics(
        {"destination": "北京", "duration": 3, "structured_preferences": {"travelers": 2}},
        [],
    )

    assert logistics["intercity_legs"] == [
        {
            "kind": "outbound",
            "origin": None,
            "destination": "北京",
            "mode": "high_speed_rail",
            "distance_km": None,
            "duration_minutes": None,
            "cost": 0.0,
            "status": "pending",
            "message": "请补充出发城市，城际交通未计入预算",
        }
    ]


def test_origin_and_return_create_estimated_round_trip_and_single_accommodation():
    logistics = build_travel_logistics(
        {
            "origin": "上海",
            "destination": "北京",
            "start_date": "2026-09-01",
            "duration": 3,
            "structured_preferences": {
                "travelers": 2,
                "hotel_preference": "mid",
                "intercity_transport": ["train"],
                "include_return": True,
            },
        },
        [],
    )

    assert [leg["kind"] for leg in logistics["intercity_legs"]] == ["outbound", "return"]
    assert all(leg["status"] == "estimated" and leg["cost"] > 0 for leg in logistics["intercity_legs"])
    assert logistics["accommodation"] == {
        "area": "北京核心交通便利区域",
        "level": "mid",
        "check_in": "2026-09-01",
        "check_out": "2026-09-03",
        "nights": 2,
        "rooms": 1,
        "nightly_rate": 450.0,
        "cost": 900.0,
        "status": "estimated",
    }


def test_local_transport_legs_use_item_locations_and_preferred_mode():
    itinerary = [
        {
            "date": "2026-09-01",
            "items": [
                {"activity": "故宫", "location": "116.397,39.918", "leg_transport_cost": 0.0},
                {"activity": "景山公园", "location": "116.396,39.925", "leg_transport_cost": 3.2},
            ],
        }
    ]

    logistics = build_travel_logistics(
        {"destination": "北京", "duration": 1, "structured_preferences": {"local_transport": ["metro"]}},
        itinerary,
    )

    assert logistics["local_transport_legs"] == [
        {
            "date": "2026-09-01",
            "from_name": "故宫",
            "to_name": "景山公园",
                "mode": "metro",
                "allowed_modes": ["metro"],
            "distance_km": None,
            "duration_minutes": None,
            "cost": 3.2,
            "status": "estimated",
            "estimate_source": "rule",
            "from_location": "116.397,39.918",
            "to_location": "116.396,39.925",
            "city": "北京",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "quote", "expected_cost"),
    [
        ("metro", {"distance_km": 1.5, "duration_minutes": 12, "cost": 4.0}, 4.0),
        ("taxi", {"distance_km": 2.1, "duration_minutes": 8, "cost": 16.5}, 16.5),
        ("ride_hailing", {"distance_km": 2.3, "duration_minutes": 9, "cost": 18.8}, 18.8),
    ],
)
async def test_enrich_local_transport_uses_amap_returned_fare_for_supported_modes(monkeypatch, mode, quote, expected_cost):
    """Breaks if a high-de map quote is replaced by distance-rate arithmetic."""
    from src.services import travel_logistics

    async def route_quote(*_args):
        return quote

    monkeypatch.setattr(travel_logistics, "amap_route_quote", route_quote)
    legs = [{
        "from_location": "116.39,39.91",
        "to_location": "116.40,39.92",
        "mode": mode,
        "allowed_modes": [mode],
        "cost": 2.0,
    }]

    result = await travel_logistics.enrich_local_transport_legs(legs)

    assert result[0]["estimate_source"] == "amap"
    assert result[0]["distance_km"] == quote["distance_km"]
    assert result[0]["duration_minutes"] == quote["duration_minutes"]
    assert result[0]["cost"] == expected_cost


@pytest.mark.asyncio
async def test_enrich_local_transport_keeps_rule_estimate_when_amap_has_no_route(monkeypatch):
    from src.services import travel_logistics

    async def no_route_quote(*_args):
        return None

    monkeypatch.setattr(travel_logistics, "amap_route_quote", no_route_quote)
    legs = [{"from_location": "116.39,39.91", "to_location": "116.40,39.92", "mode": "metro", "cost": 2.0}]

    result = await travel_logistics.enrich_local_transport_legs(legs)

    assert result[0]["estimate_source"] == "rule"
    assert result[0]["cost"] == 2.0


def test_confirm_logistics_item_marks_selected_rule_estimate_confirmed():
    from src.services.travel_logistics import confirm_logistics_item

    logistics = {
        "accommodation": {"area": "北京", "status": "estimated", "estimate_source": "rule"},
        "intercity_legs": [{"kind": "outbound", "status": "estimated", "estimate_source": "rule"}],
    }

    confirmed = confirm_logistics_item(logistics, "intercity:outbound")

    assert confirmed["intercity_legs"][0]["status"] == "confirmed"
    assert confirmed["accommodation"]["status"] == "estimated"


def test_logistics_validation_rejects_pending_intercity_cost_and_invalid_hotel_total():
    from src.graph.validator import _validate_travel_logistics

    errors = _validate_travel_logistics(
        {"duration": 3},
        {
            "intercity_legs": [{"status": "pending", "cost": 10}],
            "accommodation": {"nights": 2, "rooms": 1, "nightly_rate": 450, "cost": 800},
            "local_transport_legs": [],
        },
    )

    assert any("待补充" in error for error in errors)
    assert any("住宿费用" in error for error in errors)
