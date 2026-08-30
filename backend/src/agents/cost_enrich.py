"""行程项唯一定价引擎（enrich 为唯一确定性定价方）。

方法1：POI 精确匹配 → 写真实单价（来自 fetched_attractions / 美食 POI 的 biz_ext.cost）
方法2：相邻 item 距离 × 主交通方式费率 → 写 leg_transport_cost（到达该 item 的交通腿费）
方法3：无 POI 匹配时的属性感知估算（按 budget_level / 餐食·门票类别兜底）

约定：
- item.cost 只记「活动本身花费」（门票 / 餐费），已含 travelers 倍数。
- 交通统一记在 item.leg_transport_cost，避免与活动费冲突。
- 住宿（hotel）是行程级变量，不在每日 item 中，由 Budget Agent 按晚数×等级估算。
"""
import logging
import re
from typing import Any, Dict, List, Optional

from src.graph.state import DayPlan, TravelAgentState
from src.utils.state_utils import (
    get_budget_level,
    get_destination,
    get_local_transport,
    get_travelers,
)
from src.services.map import amap_distance_km, fetch_food_pois_with_cache
from src.services.transport_selection import select_local_transport

logger = logging.getLogger("travelmate.agents.cost_enrich")

# 方法2：交通方式 -> 每公里单价(元)
TRANSPORT_RATE_PER_KM = {
    "metro": 0.4,
    "bus": 0.25,
    "taxi": 2.6,
    "self_driving": 1.2,
    "bike": 0.0,
    "walking": 0.0,
}
# 方法3：预算等级 -> 单人单餐 / 单人门票 估算(元)
FOOD_PER_MEAL = {"economy": 45.0, "mid": 95.0, "luxury": 220.0}
TICKET_PER_ATTRACTION = {"economy": 30.0, "mid": 60.0, "luxury": 120.0}

TRANSPORT_KEYWORDS = ("机场", "车站", "地铁", "高铁", "火车", "打车", "驾车", "骑行", "步行")
MEAL_KEYWORDS = ("餐", "饭", "咖啡", "茶", "小吃", "午餐", "晚餐", "早餐", "美食", "料理")


def _travelers(state: TravelAgentState) -> int:
    try:
        return max(1, int(get_travelers(state) or 1))
    except (TypeError, ValueError):
        return 1


def _parse_amap_cost(raw: Any) -> Optional[float]:
    """biz_ext.cost 可能是 '50.00' / '人均100' / None，统一解析成 float。"""
    if raw is None:
        return None
    text = str(raw).replace("人均", "").replace("￥", "").replace("元", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def _classify_category(activity: str) -> str:
    if any(k in activity for k in TRANSPORT_KEYWORDS):
        return "transport"
    if any(k in activity for k in MEAL_KEYWORDS):
        return "food"
    if "住宿" in activity or "酒店" in activity:
        return "hotel"
    return "tickets"  # 默认视为景点门票类


def _match_poi(item: Dict[str, Any], pois: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """方法1：poi_ref 精确匹配（name/id 一致），否则按 POI name 子串匹配 activity。"""
    if not isinstance(pois, list):
        return None
    poi_ref = item.get("poi_ref")
    if poi_ref:
        for poi in pois:
            if poi.get("name") == poi_ref or poi.get("id") == poi_ref:
                return poi
    activity = str(item.get("activity", ""))
    for poi in pois:
        name = poi.get("name", "")
        if name and name in activity:
            return poi
    return None


async def _leg_transport_cost(prev: Dict[str, Any], curr: Dict[str, Any], state: TravelAgentState) -> float:
    """方法2：相邻 item 距离 × 主交通方式费率。无坐标则记 0。"""
    loc_a, loc_b = prev.get("location"), curr.get("location")
    if not loc_a or not loc_b:
        return 0.0
    km = await amap_distance_km(loc_a, loc_b)
    if not km or km <= 0:
        return 0.0
    modes = get_local_transport(state) or ["metro"]
    mode = select_local_transport(float(km), modes)
    rate = TRANSPORT_RATE_PER_KM.get(mode, 0.4)
    return round(km * rate, 2)


def _fallback_estimate(item: Dict[str, Any], state: TravelAgentState) -> float:
    """方法3：无 POI 匹配时的属性感知估算（已含 travelers 倍数）。"""
    category = _classify_category(str(item.get("activity", "")))
    level = get_budget_level(state)
    travelers = _travelers(state)
    if category == "food":
        return round(FOOD_PER_MEAL.get(level, 95.0) * travelers, 2)
    if category == "tickets":
        return round(TICKET_PER_ATTRACTION.get(level, 60.0) * travelers, 2)
    return 0.0


async def enrich_itinerary_costs(
    itinerary: List[DayPlan],
    state: TravelAgentState,
) -> List[DayPlan]:
    """遍历行程项，依次用方法1/2/3 写入定价字段。返回同一份 itinerary（就地修改）。"""
    attractions = state.get("fetched_attractions") or []
    food_pois = await fetch_food_pois_with_cache(get_destination(state))
    all_pois = list(attractions) + list(food_pois or [])
    travelers = _travelers(state)

    for day in itinerary:
        if not isinstance(day, dict):
            continue
        items = day.get("items", [])
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if item.get("status") == "completed":
                continue
            category = _classify_category(str(item.get("activity", "")))
            poi = _match_poi(item, all_pois)
            if poi:  # 方法1 命中：用 POI 真实单价
                item["poi_ref"] = poi.get("name")
                item["location"] = poi.get("location")
                price = _parse_amap_cost(poi.get("price"))
                if price is not None:
                    item["cost"] = round(price * travelers, 2)
                    item["cost_category"] = "food" if category == "food" else "tickets"
                    item["estimate_source"] = "free" if price == 0 else "amap"
                else:  # POI 无价格 -> 退方法3
                    item["cost"] = _fallback_estimate(item, state)
                    item["cost_category"] = category
                    item["estimate_source"] = "rule" if item["cost"] > 0 else "pending"
            else:  # 无匹配 -> 方法3 兜底
                item["cost"] = _fallback_estimate(item, state)
                item["cost_category"] = category
                item["estimate_source"] = "rule" if item["cost"] > 0 else "pending"
            # 方法2：到达本 item 的交通腿费（每日首 item 为 0）
            item["leg_transport_cost"] = (
                await _leg_transport_cost(items[idx - 1], item, state) if idx > 0 else 0.0
            )
    return itinerary
