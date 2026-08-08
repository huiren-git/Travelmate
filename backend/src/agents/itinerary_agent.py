"""Itinerary Agent: 使用 LLM 生成或调整行程。"""

import json
import logging
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import DayPlan, ItineraryItem, TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, ensure_list, extract_json, message_content
from src.utils.state_utils import (
    get_current_time,
    get_daily_itinerary,
    get_destination,
    get_duration,
    get_plan_mode,
    get_start_date,
    get_start_date_text,
    get_structured_preferences,
    parse_time_to_minutes,
)

logger = logging.getLogger("travelmate.agents.itinerary")
LOCKED_STATUSES = {"completed", "ongoing"}


# 获取行程 Agent 使用的 LLM 实例。
def get_itinerary_llm():
    from src.agents.base import get_llm

    return get_llm(temperature=0.4)


# 解析前端传入的 current_time 时间锚点。
def _parse_current_datetime(current_time: Any) -> Optional[datetime]:
    if not isinstance(current_time, str):
        return None
    value = current_time.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value), time.min)
        except ValueError:
            return None
    return parsed.replace(tzinfo=None)


# 将单个行程项的 date 与 time 合并成可比较的 datetime。
def _item_datetime(day: Dict[str, Any], item: Dict[str, Any]) -> Optional[datetime]:
    day_date = _as_text(day.get("date"), "")
    minutes = parse_time_to_minutes(item.get("time"))
    if not day_date or minutes < 0:
        return None
    try:
        parsed_date = date.fromisoformat(day_date)
    except ValueError:
        return None
    return datetime.combine(parsed_date, time(minutes // 60, minutes % 60))


# 判断行程项是否因为状态或 current_time 进入锁定区。
def _is_time_locked(
    day: Dict[str, Any],
    item: Dict[str, Any],
    current_dt: Optional[datetime],
) -> bool:
    item_dt = _item_datetime(day, item)
    return bool(current_dt and item_dt and item_dt < current_dt)


# 判断原始行程项是否因为状态或 current_time 进入锁定区。
def _is_locked_item(
    day: Dict[str, Any],
    item: Dict[str, Any],
    current_dt: Optional[datetime],
) -> bool:
    if item.get("status") in LOCKED_STATUSES:
        return True
    return _is_time_locked(day, item, current_dt)


# 判断单日行程中是否仍有可以交给 LLM 修改的项目。
def _has_editable_items(day: Dict[str, Any], current_dt: Optional[datetime]) -> bool:
    return any(
        not _is_locked_item(day, item, current_dt)
        for item in ensure_list(day.get("items", []), "items")
        if isinstance(item, dict)
    )


# 将锁定行程压缩为只给 LLM 避让使用的摘要。
def _locked_item_summary(day: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "day": day.get("day"),
        "date": day.get("date"),
        "time": item.get("time"),
        "activity": item.get("activity"),
        "status": item.get("status"),
    }


# 构造 REPLAN 模式下只包含开放区的提示词上下文。
def _replan_payload(state: TravelAgentState) -> Dict[str, Any]:
    current_dt = _parse_current_datetime(get_current_time(state))
    locked_items = []
    editable_itinerary = []
    for day in get_daily_itinerary(state):
        if not isinstance(day, dict):
            continue
        locked_day_items = []
        editable_day_items = []
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            if _is_locked_item(day, item, current_dt):
                locked_day_items.append(_locked_item_summary(day, item))
            else:
                editable_day_items.append(deepcopy(item))

        locked_items.extend(locked_day_items)
        if editable_day_items:
            editable_itinerary.append(
                {
                    "day": day.get("day"),
                    "date": day.get("date"),
                    "items": editable_day_items,
                }
            )

    return {
        "current_time": get_current_time(state),
        "locked_items": locked_items,
        "editable_itinerary": editable_itinerary,
    }


# 将当前 State 压缩为适合提示词使用的上下文。
def _state_payload(state: TravelAgentState) -> Dict[str, Any]:
    mode = get_plan_mode(state)
    payload = {
        "plan_mode": mode,
        "mode": mode,
        "destination": get_destination(state),
        "start_date": get_start_date_text(state),
        "duration": get_duration(state),
        "current_time": get_current_time(state),
        "preferences": get_structured_preferences(state),
        "weather_info": state.get("weather_info"),
        "fetched_attractions": state.get("fetched_attractions"),
        "validation_report": state.get("validation_report"),
        "existing_itinerary": get_daily_itinerary(state),
    }
    if mode == "replan":
        payload.update(_replan_payload(state))
        payload.pop("existing_itinerary", None)
    return payload


# 构造要求 LLM 返回行程 JSON 的消息列表。
def _build_itinerary_messages(state: TravelAgentState) -> list[Any]:
    system_prompt = """
你是 TravelMate 的 Itinerary Agent，只负责生成或调整 daily_itinerary，不处理预算。
请只返回 JSON，不要返回 Markdown 或额外解释。
JSON schema:
{
  "daily_itinerary": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "items": [
        {
          "time": "09:00",
          "activity": "景点或活动名称",
          "duration": "2h",
          "address": "详细地址",
          "status": "completed | ongoing | upcoming",
          "tips": "购票、交通、天气或避坑提示"
        }
      ]
    }
  ]
}
规则：
- PLAN 模式下生成天数等于 duration 的完整行程。
- REPLAN 模式下只基于 editable_itinerary 重新规划开放区，locked_items 由后端原样合并。
- ItineraryItem.status 是硬边界：completed 和 ongoing 项严禁输出、改写、删除或重排。
- current_time 是逻辑锁：早于 current_time 的项目全部锁定，晚于或等于 current_time 的 upcoming 项才允许修改。
- REPLAN 模式下不要重复输出已完成的行程；只返回未来开放区项目，且这些项目 status 必须是 upcoming。
- 优先利用 fetched_attractions、weather_info 和 preferences。
- 不要返回 budget 字段。
""".strip()
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(_state_payload(state), ensure_ascii=False)),
    ]


# 将任意值转换成字符串，缺失时使用默认值。
def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


# 规范化单个行程项，保证符合 ItineraryItem 字段要求。
def _normalize_item(raw: Any) -> ItineraryItem:
    item = ensure_dict(raw, "itinerary item")
    status = _as_text(item.get("status"), "upcoming")
    if status not in {"completed", "ongoing", "upcoming"}:
        status = "upcoming"

    return {
        "time": _as_text(item.get("time"), "09:00"),
        "activity": _as_text(item.get("activity"), "待定活动"),
        "duration": _as_text(item.get("duration"), "1h"),
        "address": _as_text(item.get("address"), ""),
        "status": status,
        "tips": _as_text(item.get("tips"), ""),
    }


# 规范化单日行程，补齐 day、date 和 items。
def _normalize_day(raw: Any, fallback_day: int, fallback_date: str) -> DayPlan:
    day = ensure_dict(raw, "day plan")
    items = [_normalize_item(item) for item in ensure_list(day.get("items", []), "items")]
    if not items:
        raise ValueError(f"day {fallback_day} must contain at least one itinerary item")

    try:
        day_number = int(day.get("day") or fallback_day)
    except (TypeError, ValueError):
        day_number = fallback_day

    return {
        "day": day_number,
        "date": _as_text(day.get("date"), fallback_date),
        "items": items,
    }


# 从 LLM 响应中提取并规范化完整行程列表。
def _normalize_itinerary(raw: Dict[str, Any], state: TravelAgentState) -> List[DayPlan]:
    raw_days = ensure_list(raw.get("daily_itinerary"), "daily_itinerary")
    start = get_start_date(state)
    normalized = []
    for index, raw_day in enumerate(raw_days, start=1):
        fallback_date = (start + timedelta(days=index - 1)).isoformat()
        normalized.append(_normalize_day(raw_day, index, fallback_date))

    if not normalized:
        raise ValueError("daily_itinerary must not be empty")
    return normalized


# 获取行程项用于去重的活动名称。
def _activity_key(item: Dict[str, Any]) -> str:
    return _as_text(item.get("activity"), "").casefold()


# 安全读取单日行程的 day 编号。
def _day_number(day: Dict[str, Any]) -> Optional[int]:
    try:
        parsed = int(day.get("day"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


# 判断 LLM 产出的项目是否重复了锁定行程。
def _duplicates_locked_item(
    day: Dict[str, Any],
    item: Dict[str, Any],
    locked_items: List[Dict[str, Any]],
) -> bool:
    day_date = _as_text(day.get("date"), "")
    item_time = _as_text(item.get("time"), "")
    item_activity = _activity_key(item)
    for locked_item in locked_items:
        locked_date = _as_text(locked_item.get("date"), "")
        if day_date != locked_date:
            continue
        if item_time and item_time == _as_text(locked_item.get("time"), ""):
            return True
        if item_activity and item_activity == _activity_key(locked_item):
            return True
    return False


# 按时间对单日行程项排序，非法时间放到最后。
def _sort_items_by_time(items: List[ItineraryItem]) -> List[ItineraryItem]:
    return sorted(
        items,
        key=lambda item: (
            parse_time_to_minutes(item.get("time")) < 0,
            parse_time_to_minutes(item.get("time")),
        ),
    )


# 合并 REPLAN 模式下的锁定行程和 LLM 生成的开放区行程。
def _merge_replan_itinerary(
    llm_itinerary: List[DayPlan],
    state: TravelAgentState,
) -> List[DayPlan]:
    current_dt = _parse_current_datetime(get_current_time(state))
    existing_days = {}
    for day in get_daily_itinerary(state):
        if not isinstance(day, dict):
            continue
        day_number = _day_number(day)
        if day_number is not None:
            existing_days[day_number] = deepcopy(day)
    generated_days = {day["day"]: day for day in llm_itinerary}
    start = get_start_date(state)
    day_numbers = sorted(set(existing_days) | set(generated_days))
    merged = []

    for day_number in day_numbers:
        existing_day = existing_days.get(day_number)
        generated_day = generated_days.get(day_number)
        fallback_date = (start + timedelta(days=day_number - 1)).isoformat()
        base_day = existing_day or generated_day or {}
        date_text = _as_text(base_day.get("date"), fallback_date)
        locked_items = [
            deepcopy(item)
            for item in ensure_list((existing_day or {}).get("items", []), "items")
            if isinstance(item, dict) and _is_locked_item(existing_day or {}, item, current_dt)
        ]
        locked_refs = [
            _locked_item_summary({"day": day_number, "date": date_text}, item)
            for item in locked_items
        ]

        if generated_day is None:
            editable_items = [
                deepcopy(item)
                for item in ensure_list((existing_day or {}).get("items", []), "items")
                if isinstance(item, dict) and not _is_locked_item(existing_day or {}, item, current_dt)
            ]
        else:
            editable_items = []
            for item in generated_day.get("items", []):
                if _is_time_locked(generated_day, item, current_dt):
                    continue
                if _duplicates_locked_item(generated_day, item, locked_refs):
                    continue
                copied_item = deepcopy(item)
                copied_item["status"] = "upcoming"
                editable_items.append(copied_item)

        items = _sort_items_by_time(locked_items + editable_items)
        if items:
            merged.append({"day": day_number, "date": date_text, "items": items})

    if not merged:
        raise ValueError("daily_itinerary must not be empty")
    return merged


# 判断 REPLAN 模式是否存在可以交给 LLM 修改的开放区。
def _has_replan_editable_scope(state: TravelAgentState) -> bool:
    current_dt = _parse_current_datetime(get_current_time(state))
    return any(
        isinstance(day, dict) and _has_editable_items(day, current_dt)
        for day in get_daily_itinerary(state)
    )


# 调用 LLM 生成行程，并将结果写回 State。
async def itinerary_agent_node(state: TravelAgentState) -> Dict[str, Any]:
    mode = get_plan_mode(state)
    logger.info("Running LLM itinerary node, mode=%s", mode)

    if mode == "replan" and get_daily_itinerary(state) and not _has_replan_editable_scope(state):
        return {
            "draft_daily_itinerary": deepcopy(get_daily_itinerary(state)),
            "plan_mode": mode,
            "current_mode": mode,
            "validation_attempts": 0,
        }

    llm = get_itinerary_llm()
    response = await call_llm(llm, _build_itinerary_messages(state))
    parsed = ensure_dict(extract_json(message_content(response)), "itinerary response")
    itinerary = _normalize_itinerary(parsed, state)
    if mode == "replan" and get_daily_itinerary(state):
        itinerary = _merge_replan_itinerary(itinerary, state)
        return {
            "draft_daily_itinerary": itinerary,
            "plan_mode": mode,
            "current_mode": mode,
            "validation_attempts": 0,
        }

    return {
        "daily_itinerary": itinerary,
        "draft_daily_itinerary": None,
        "plan_mode": mode,
        "current_mode": mode,
        "validation_attempts": 0,
    }
