"""Deterministic blueprint adaptation; intentionally contains no LLM calls."""

from datetime import date, timedelta
from typing import Any

from src.services.weather import fetch_weather_with_cache
from src.services.map import fetch_attractions_with_cache, fetch_poi_detail

async def find_poi(city: str, name: str) -> dict[str, Any] | None:
    """优先通过名称查询 POI 详情；失败时兼容旧的景点缓存匹配。"""
    poi = await fetch_poi_detail(city, name)
    if poi:
        return poi
    pois = await fetch_attractions_with_cache(city, limit=20)
    return next((item for item in pois if item.get("name") == name), None)

async def find_replacement_poi(city: str, name: str, indoor: bool) -> dict[str, Any] | None:
    pois = await fetch_attractions_with_cache(city, limit=20)
    indoor_words = ("博物馆", "美术馆", "剧院", "展览")
    candidates = [poi for poi in pois if poi.get("name") != name and (not indoor or any(word in str(poi.get("name")) for word in indoor_words))]
    return candidates[0] if candidates else None


def _duration(value: str) -> int:
    try:
        return max(1, int(str(value).lower().replace("h", "").strip()))
    except ValueError:
        return 1


def build_reference_budget(
    itinerary: list[dict[str, Any]],
    logistics: dict[str, Any],
    level: str,
) -> dict[str, Any]:
    """从采纳后已补全的行程项与交通住宿方案生成确定性预算。"""
    detail = {"food": 0.0, "tickets": 0.0}
    for day in itinerary:
        for item in day.get("items") or []:
            category = item.get("cost_category")
            if category in detail:
                detail[category] += float(item.get("cost") or 0.0)
    detail["intercity_transport"] = sum(float(leg.get("cost") or 0.0) for leg in logistics.get("intercity_legs") or [])
    detail["local_transport"] = sum(float(leg.get("cost") or 0.0) for leg in logistics.get("local_transport_legs") or [])
    detail["hotel"] = float((logistics.get("accommodation") or {}).get("cost") or 0.0)
    detail = {key: round(value, 2) for key, value in detail.items()}
    return {
        "level": level if level in {"economy", "mid", "luxury"} else "mid",
        "total": round(sum(detail.values()), 2),
        "detail": detail,
        "saving_tips": [],
    }


async def adapt_reference_trip(reference: dict[str, Any], *, duration: int, start_date: str, travelers: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sequence = list(reference.get("sequence") or [])
    rhythm = list(reference.get("rhythm") or [])
    log: list[dict[str, Any]] = []
    original_days = int(reference.get("duration") or len(sequence) or 1)
    if duration < original_days:
        keep = max(duration, min(len(sequence), duration * max(1, len(sequence) // original_days)))
        sequence, rhythm = sequence[:keep], rhythm[:keep]
        log.append({"kind": "duration_compressed", "from": original_days, "to": duration})
    city = str(reference.get("destination") or "")
    weather = await fetch_weather_with_cache(city)
    severe = any(word in str(weather.get("desc") or "") for word in ("暴雨", "暴雪"))
    adapted: list[tuple[str, dict[str, Any] | None]] = []
    for activity in sequence:
        poi = await find_poi(city, activity)
        closed = "关闭" in str((poi or {}).get("business") or "") or "休息" in str((poi or {}).get("business") or "")
        replacement = None
        if closed:
            replacement = await find_replacement_poi(city, activity, severe)
            log.append({"kind": "closed_replaced" if replacement else "risk_retained", "from": activity, "to": (replacement or {}).get("name")})
        if severe:
            indoor = await find_replacement_poi(city, activity, True)
            replacement = indoor or replacement
            log.append({"kind": "weather_replaced" if indoor else "risk_retained", "from": activity, "to": (indoor or {}).get("name")})
        selected_poi = replacement or poi
        adapted.append(((selected_poi or {}).get("name") or activity, selected_poi))
    days = [{"day": index + 1, "date": (date.fromisoformat(start_date) + timedelta(days=index)).isoformat(), "items": []} for index in range(duration)]
    current_minutes = [9 * 60] * duration
    resolved_pois: list[dict[str, Any]] = []
    for index, (activity, poi) in enumerate(adapted):
        day = index % duration
        hours = _duration(rhythm[index] if index < len(rhythm) else "1h")
        start = current_minutes[day]
        if poi:
            resolved_pois.append(poi)
        days[day]["items"].append({
            "time": f"{start // 60:02d}:{start % 60:02d}",
            "activity": activity,
            "duration": f"{hours}h",
            "status": "upcoming",
            "address": (poi or {}).get("address"),
            "location": (poi or {}).get("location"),
            "image_url": (poi or {}).get("image_url") or "",
            "poi_ref": (poi or {}).get("name"),
            "tips": None,
        })
        current_minutes[day] += hours * 60
    budget = dict(reference.get("budget") or {})
    source_travelers = int(reference.get("travelers") or 2)
    factor = travelers / source_travelers
    if budget:
        budget["total"] = round(float(budget.get("total") or 0) * factor, 2)
        budget["detail"] = {key: round(float(value) * factor, 2) for key, value in (budget.get("detail") or {}).items()}
        log.append({"kind": "budget_scaled", "from": source_travelers, "to": travelers, "factor": factor})
    return {
        "draft_daily_itinerary": days,
        "draft_budget": budget,
        "fetched_attractions": resolved_pois,
        "weather_info": weather,
        "adaptation_log": log,
    }, log
