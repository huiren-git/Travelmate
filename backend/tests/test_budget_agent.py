from src.agents.budget_agent import _flip_budget_from_items


def test_budget_splits_intercity_and_local_transport_and_reuses_logistics_hotel():
    state = {
        "origin": "上海",
        "destination": "北京",
        "start_date": "2026-09-01",
        "duration": 2,
        "structured_preferences": {"travelers": 2, "include_return": True, "intercity_transport": ["train"]},
    }
    itinerary = [{"date": "2026-09-01", "items": [
        {"cost": 50.0, "cost_category": "tickets", "leg_transport_cost": 0.0},
        {"cost": 20.0, "cost_category": "food", "leg_transport_cost": 3.5},
    ]}]

    detail = _flip_budget_from_items(itinerary, state)

    state["travel_logistics"] = {"local_transport_legs": [{"cost": 19.5}]}
    detail = _flip_budget_from_items(itinerary, state)

    assert detail["local_transport"] == 19.5
    assert detail["intercity_transport"] > 0
    assert detail["hotel"] == 450.0
    assert set(detail) == {"intercity_transport", "local_transport", "hotel", "food", "tickets"}
