"""Helpers for reading and normalizing TravelAgentState values."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from src.graph.state import TravelAgentState

DEFAULT_START_DATE = date(2026, 8, 10)
DEFAULT_DESTINATION = "目的地"
ALLOWED_BUDGET_LEVELS = {"economy", "mid", "luxury"}
ALLOWED_MODES = {"plan", "replan"}


# 将任意值转换为正整数，失败时返回默认值。
def as_positive_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


# 将任意值规范化为非空字符串，失败时返回默认值。
def normalized_text(value: Any, default: Optional[str] = None) -> Optional[str]:
    if not isinstance(value, str):
        return default
    value = value.strip()
    return value or default


# 获取结构化偏好字段，缺失或类型不对时返回空字典。
def get_structured_preferences(state: TravelAgentState) -> Dict[str, Any]:
    preferences = state.get("structured_preferences") or {}
    return preferences if isinstance(preferences, dict) else {}


# 获取目的地字段，缺失时使用默认目的地。
def get_destination(state: TravelAgentState, default: Optional[str] = DEFAULT_DESTINATION) -> Optional[str]:
    return normalized_text(state.get("destination"), default)


# 获取出发地字段，缺失时返回默认值。
def get_origin(state: TravelAgentState, default: Optional[str] = None) -> Optional[str]:
    return normalized_text(state.get("origin"), default)


# 获取旅行天数，缺失时返回默认天数。
def get_duration(state: TravelAgentState, default: int = 1) -> int:
    return as_positive_int(state.get("duration"), default) or default


# 获取可选旅行天数，缺失时返回 None。
def get_optional_duration(state: TravelAgentState) -> Optional[int]:
    return as_positive_int(state.get("duration"), None)


# 获取出发日期对象，格式非法时返回默认日期。
def get_start_date(state: TravelAgentState, default: date = DEFAULT_START_DATE) -> date:
    raw = state.get("start_date")
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return default


# 获取出发日期文本，缺失时返回默认值。
def get_start_date_text(state: TravelAgentState, default: Optional[str] = None) -> Optional[str]:
    raw = normalized_text(state.get("start_date"), None)
    return raw if raw is not None else default


# 获取当前规划模式，优先读取 plan_mode 并兼容旧的 current_mode。
def get_plan_mode(state: TravelAgentState, default: str = "plan") -> str:
    mode = state.get("plan_mode") or state.get("current_mode")
    return mode if mode in ALLOWED_MODES else default


# 获取当前规划模式，兼容旧调用点。
def get_current_mode(state: TravelAgentState, default: str = "plan") -> str:
    return get_plan_mode(state, default)


# 获取当前时间锚点，缺失时返回默认值。
def get_current_time(state: TravelAgentState, default: Optional[str] = None) -> Optional[str]:
    return normalized_text(state.get("current_time"), default)


# 获取预算等级偏好，非法时回退到默认等级。
def get_budget_level(state: TravelAgentState, default: str = "mid") -> str:
    preferences = get_structured_preferences(state)
    level = preferences.get("budget_level") or preferences.get("level")
    return level if level in ALLOWED_BUDGET_LEVELS else default


# 获取旅行人数偏好，缺失时返回默认人数。
def get_travelers(state: TravelAgentState, default: int = 1) -> int:
    preferences = get_structured_preferences(state)
    for key in ("travelers", "traveler_count", "travelers_count"):
        travelers = as_positive_int(preferences.get(key), None)
        if travelers is not None:
            return travelers
    return default


# 获取行程节奏偏好，缺失时返回默认节奏。
def get_pace(state: TravelAgentState, default: str = "relaxed") -> str:
    preferences = get_structured_preferences(state)
    pace = preferences.get("pace")
    return pace if isinstance(pace, str) and pace else default


# 获取每日行程列表，缺失或类型不对时返回空列表。
def get_daily_itinerary(state: TravelAgentState) -> List[Dict[str, Any]]:
    itinerary = state.get("daily_itinerary") or []
    return itinerary if isinstance(itinerary, list) else []


# 获取草稿每日行程列表，缺失或类型不对时返回空列表。
def get_draft_daily_itinerary(state: TravelAgentState) -> List[Dict[str, Any]]:
    itinerary = state.get("draft_daily_itinerary") or []
    return itinerary if isinstance(itinerary, list) else []


# 获取预算对象，缺失或类型不对时返回空字典。
def get_budget(state: TravelAgentState) -> Dict[str, Any]:
    budget = state.get("budget") or {}
    return budget if isinstance(budget, dict) else {}


# 获取校验次数，缺失时返回零。
def get_validation_attempts(state: TravelAgentState) -> int:
    return as_positive_int(state.get("validation_attempts"), 0) or 0


# 获取硬校验重试次数，缺失时返回零。
def get_hard_validation_attempts(state: TravelAgentState) -> int:
    return as_positive_int(state.get("hard_validation_attempts"), 0) or 0


# 获取软评估重试次数，缺失时返回零。
def get_soft_validation_attempts(state: TravelAgentState) -> int:
    return as_positive_int(state.get("soft_validation_attempts"), 0) or 0


# 判断当前 State 是否已有每日行程。
def has_daily_itinerary(state: TravelAgentState) -> bool:
    return bool(get_daily_itinerary(state))


# 判断当前 State 是否已有草稿每日行程。
def has_draft_daily_itinerary(state: TravelAgentState) -> bool:
    return bool(get_draft_daily_itinerary(state))


# 判断当前 State 是否已有预算。
def has_budget(state: TravelAgentState) -> bool:
    return bool(get_budget(state))


# 将 HH:MM 时间转换为当天分钟数，非法时返回 -1。
def parse_time_to_minutes(time_str: Any) -> int:
    if not isinstance(time_str, str):
        return -1
    try:
        hours, minutes = map(int, time_str.split(":"))
    except ValueError:
        return -1
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return -1
    return hours * 60 + minutes


# 将 2h、90m 或数值时长转换为分钟数。
def parse_duration_to_minutes(duration: Any) -> int:
    if isinstance(duration, (int, float)):
        return max(0, int(duration))
    if not isinstance(duration, str):
        return 0

    value = duration.strip().lower()
    if not value:
        return 0

    try:
        if value.endswith("h"):
            return max(0, int(float(value[:-1].strip()) * 60))
        if value.endswith("m"):
            return max(0, int(float(value[:-1].strip())))
        return max(0, int(float(value)))
    except ValueError:
        return 0


# 从多个候选值中返回第一个非空值。
def first_present(values: Iterable[Any], default: Any = None) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return default
