"""LLM-free feasibility check for adopted reference itineraries."""
from typing import Any, Dict
from src.utils.state_utils import parse_duration_to_minutes, parse_time_to_minutes

async def reference_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    days = state.get("draft_daily_itinerary") or []
    expected = state.get("duration")
    errors = []
    if not days or (expected and len(days) != expected): errors.append("daily itinerary day count is invalid")
    for day in days:
        end = -1
        for item in day.get("items") or []:
            try:
                start = parse_time_to_minutes(item.get("time"))
                duration = parse_duration_to_minutes(item.get("duration"))
                if not item.get("activity") or duration <= 0 or start < end: errors.append("itinerary time conflict or invalid item")
                end = max(end, start + duration)
            except Exception: errors.append("itinerary time conflict or invalid item")
    passed = not errors
    update = {"is_finished": True, "terminal_status": "confirmed" if passed else "failed", "validation_report": {"passed": passed, "score": 100 if passed else 0, "errors": errors, "warnings": []}, "failure_reason": "; ".join(errors) or None}
    if passed: update.update({"daily_itinerary": days, "budget": state.get("draft_budget"), "draft_daily_itinerary": None, "draft_budget": None})
    return update
