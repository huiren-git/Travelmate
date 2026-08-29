"""确定性生成单目的地行程的交通与住宿估算。"""

from __future__ import annotations

from datetime import date, timedelta
from copy import deepcopy
from typing import Any

from src.utils.state_utils import (
    get_destination,
    get_duration,
    get_hotel_preference,
    get_lodging_mode,
    get_intercity_transport,
    get_local_transport,
    get_origin,
    get_start_date,
    get_travelers,
)
from src.services.map import amap_route_quote
from src.services.transport_selection import select_local_transport


_INTERCITY_MODE_DEFAULT = "high_speed_rail"
_INTERCITY_MODE_ALIASES = {"train": "high_speed_rail", "flight": "flight", "self_driving": "self_driving"}
_INTERCITY_RATE_PER_KM = {"high_speed_rail": 0.55, "flight": 0.85, "self_driving": 0.75}
_INTERCITY_SPEED_KPH = {"high_speed_rail": 220.0, "flight": 650.0, "self_driving": 80.0}
_CITY_COORDINATES = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668),
    "西安": (34.3416, 108.9398),
}
_HOTEL_RATES = {"economy": 200.0, "mid": 450.0, "luxury": 1000.0}
_LOCAL_TRANSPORT_RATE_PER_KM = {"metro": 0.4, "bus": 0.25, "taxi": 2.6, "ride_hailing": 2.6, "self_driving": 1.2, "bike": 0.0, "walking": 0.0}


def _intercity_mode(state: dict[str, Any]) -> str:
    choices = get_intercity_transport(state)
    return _INTERCITY_MODE_ALIASES.get(choices[0], _INTERCITY_MODE_DEFAULT) if choices else _INTERCITY_MODE_DEFAULT


def _estimated_intercity_leg(kind: str, origin: str, destination: str, mode: str, travelers: int) -> dict[str, Any]:
    # 本期不引入外部地图/票务服务；城市坐标未知时保留可见但未计价的待补充段。
    if origin not in _CITY_COORDINATES or destination not in _CITY_COORDINATES:
        return {
            "kind": kind, "origin": origin, "destination": destination, "mode": mode,
            "distance_km": None, "duration_minutes": None, "cost": 0.0,
            "status": "pending", "message": "暂无法估算该城际路线，未计入预算",
        }
    lat_a, lng_a = _CITY_COORDINATES[origin]
    lat_b, lng_b = _CITY_COORDINATES[destination]
    # 足够稳定的首期近似：经纬度差换算为城市间直线距离，并以交通方式估价。
    distance = round((((lat_a - lat_b) * 111) ** 2 + ((lng_a - lng_b) * 96) ** 2) ** 0.5)
    return {
        "kind": kind,
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "distance_km": distance,
        "duration_minutes": round(distance / _INTERCITY_SPEED_KPH[mode] * 60),
        "cost": round(distance * _INTERCITY_RATE_PER_KM[mode] * travelers, 2),
        "status": "estimated",
        "message": "规则估算，实际票价以预订时为准",
    }


def _intercity_legs(state: dict[str, Any]) -> list[dict[str, Any]]:
    origin, destination = get_origin(state), get_destination(state)
    mode = _intercity_mode(state)
    travelers = max(1, get_travelers(state))
    if not origin:
        return [{
            "kind": "outbound", "origin": None, "destination": destination, "mode": mode,
            "distance_km": None, "duration_minutes": None, "cost": 0.0,
            "status": "pending", "message": "请补充出发城市，城际交通未计入预算",
        }]
    legs = [_estimated_intercity_leg("outbound", origin, destination, mode, travelers)]
    preferences = state.get("structured_preferences") or {}
    if preferences.get("include_return", True):
        legs.append(_estimated_intercity_leg("return", destination, origin, mode, travelers))
    return legs


def _accommodation(state: dict[str, Any]) -> dict[str, Any]:
    if get_lodging_mode(state) == "home":
        return {
            "mode": "home",
            "area": "住家里",
            "nights": 0,
            "rooms": 0,
            "nightly_rate": 0.0,
            "cost": 0.0,
            "status": "not_required",
        }
    duration = get_duration(state)
    nights = max(1, duration - 1)
    travelers = max(1, get_travelers(state))
    level = get_hotel_preference(state) or "mid"
    rooms = max(1, (travelers + 1) // 2)
    check_in = get_start_date(state)
    rate = _HOTEL_RATES.get(level, _HOTEL_RATES["mid"])
    return {
        "mode": "hotel",
        "area": f"{get_destination(state)}核心交通便利区域",
        "level": level,
        "check_in": check_in.isoformat(),
        "check_out": (check_in + timedelta(days=nights)).isoformat(),
        "nights": nights,
        "rooms": rooms,
        "nightly_rate": rate,
        "cost": round(nights * rooms * rate, 2),
        "status": "estimated",
    }


def _local_transport_legs(state: dict[str, Any], itinerary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将每日相邻景点转换为待高德路线服务补全的市内交通段。"""
    modes = get_local_transport(state)
    legs: list[dict[str, Any]] = []
    for day in itinerary:
        items = day.get("items") if isinstance(day, dict) else None
        if not isinstance(items, list):
            continue
        for previous, current in zip(items, items[1:]):
            if not isinstance(previous, dict) or not isinstance(current, dict):
                continue
            legs.append({
                "date": day.get("date"),
                "from_name": previous.get("activity", "上一站"),
                "to_name": current.get("activity", "下一站"),
                "mode": select_local_transport(0, modes),
                "allowed_modes": modes or ["walking", "metro", "bus", "taxi"],
                "distance_km": None,
                "duration_minutes": None,
                "cost": round(float(current.get("leg_transport_cost") or 0.0), 2),
                "status": "estimated",
                "estimate_source": "rule",
                "from_location": previous.get("location"),
                "to_location": current.get("location"),
                "city": get_destination(state),
            })
    return legs


async def enrich_local_transport_legs(legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用高德路线费用补齐市内交通段；调用失败时保留原规则估算。"""
    for leg in legs:
        origin, destination = leg.get("from_location"), leg.get("to_location")
        if not origin or not destination:
            leg.setdefault("estimate_source", "rule")
            continue
        try:
            mode = select_local_transport(0, leg.get("allowed_modes") or [leg.get("mode")])
            quote = await amap_route_quote(origin, destination, mode, leg.get("city"))
        except Exception:
            quote = None
        if not quote:
            leg.setdefault("estimate_source", "rule")
            continue
        leg["mode"] = mode
        leg["distance_km"] = quote["distance_km"]
        leg["duration_minutes"] = quote["duration_minutes"]
        leg["cost"] = quote["cost"]
        leg["estimate_source"] = "amap"
    return legs


def confirm_logistics_item(logistics: dict[str, Any], item_key: str) -> dict[str, Any]:
    """确认一项规则估算方案；调用方负责将结果持久化到会话状态。"""
    result = deepcopy(logistics)
    if item_key == "accommodation" and isinstance(result.get("accommodation"), dict):
        result["accommodation"]["status"] = "confirmed"
        return result
    if item_key.startswith("intercity:"):
        kind = item_key.split(":", 1)[1]
        for leg in result.get("intercity_legs") or []:
            if leg.get("kind") == kind:
                leg["status"] = "confirmed"
                return result
    raise ValueError("unknown logistics item")


def build_travel_logistics(state: dict[str, Any], itinerary: list[dict[str, Any]]) -> dict[str, Any]:
    """返回前端可直接消费的全程交通、住宿与市内交通段。"""
    return {
        "origin": get_origin(state),
        "destination": get_destination(state),
        "include_return": bool((state.get("structured_preferences") or {}).get("include_return", True)),
        "intercity_legs": _intercity_legs(state),
        "accommodation": _accommodation(state),
        "local_transport_legs": _local_transport_legs(state, itinerary),
    }
