"""Itinerary Agent: 使用 LLM 生成或调整行程。"""

import asyncio
import json
import logging
import re
from hashlib import sha256
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.exceptions import raise_itinerary_image_not_found
from src.agents.cost_enrich import enrich_itinerary_costs
from src.graph.state import DayPlan, ItineraryItem, TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, ensure_list, extract_json, message_content
from src.utils.state_utils import (
    as_positive_int,
    get_current_time,
    get_daily_itinerary,
    get_destination,
    get_duration,
    get_hotel_preference,
    get_interests,
    get_local_transport,
    get_pace,
    get_plan_mode,
    get_start_date,
    get_start_date_text,
    get_structured_preferences,
    parse_time_to_minutes,
)

from src.core.tracing import trace_span

logger = logging.getLogger("travelmate.agents.itinerary")
LOCKED_STATUSES = {"completed", "ongoing"}
PREFERENCE_MARKERS = (
    "喜欢",
    "偏好",
    "希望",
    "不喜欢",
    "不要太",
    "尽量",
    "优先",
    "适合",
    "轻松",
    "慢节奏",
    "休息",
)
ACTION_MARKERS = (
    "换成",
    "换一个",
    "改成",
    "调整",
    "重排",
    "取消",
    "删除",
    "别去",
    "不去",
    "接受",
    "拒绝",
)
_STORED_MEMORY_KEYS: set[str] = set()


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
    # current_time 可能以 UTC 传入（浏览器 toISOString() 带 Z，例如
    # 2026-08-21T05:48:27.960Z 实际是中国时间 13:48）。行程项时间是“中国本地
    # 墙钟时间”(naive, 如 14:00)。若直接抹掉时区，13:48 会被误读成 05:48，
    # 使所有行程项都不触发时间锁，整个行程被当作可编辑区重写。
    # 因此带时区的入参须先换算成中国本地时间(UTC+8)再去掉时区信息；
    # naive 入参（本地时间）走原逻辑，行为不变。
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return parsed


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
# scope 非 None 时，作用域外的未来项也视为锁定——这样 _replan_payload（给 LLM 的
# 可编辑区）与 _merge_replan_itinerary（回填）共用这一个谓词，两侧会同时生效：
# LLM 看不到的项，merge 时从 existing_day 原样 deepcopy 回填（image_url/cost 全保真）。
def _is_locked_item(
    day: Dict[str, Any],
    item: Dict[str, Any],
    current_dt: Optional[datetime],
    scope: Optional[Dict[str, Any]] = None,
) -> bool:
    if item.get("status") in LOCKED_STATUSES:
        return True
    if _is_time_locked(day, item, current_dt):
        return True
    return scope is not None and not _in_replan_scope(day, item, scope)


# 判断单日行程中是否仍有可以交给 LLM 修改的项目。
def _has_editable_items(
    day: Dict[str, Any],
    current_dt: Optional[datetime],
    scope: Optional[Dict[str, Any]] = None,
) -> bool:
    return any(
        not _is_locked_item(day, item, current_dt, scope)
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


# ============================================================
# REPLAN 作用域解析：把“用户本轮到底要改什么”收敛成机器可判的结构。
# 三级收敛：点名项 → 点名日期 → 全开放区（= 旧行为，向后兼容）。
# scope 会让 _is_locked_item 把“范围外的未来项”也判为锁定，
# 于是 _replan_payload（给 LLM 的可编辑区）与 _merge_replan_itinerary（回填）
# 共用一套保护：LLM 看不到的项，merge 时原样 deepcopy 回填（image_url/cost 全保真）。
# ============================================================
SCOPE_TARGET_MARKERS = ("行程", "安排", "计划", "活动", "景点", "路线", "日程")
RELATIVE_DAY_OFFSETS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}
CN_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


# 兜底作用域：授权改全部开放区，等价于旧行为。
def _scope_all(instruction: str = "") -> Dict[str, Any]:
    return {"kind": "all", "target_dates": [], "target_days": [],
            "target_item_keys": [], "instruction": instruction}


# 行程项在作用域内的唯一键：日期 + 时间。
def _item_scope_key(day: Dict[str, Any], item: Dict[str, Any]) -> str:
    return f"{_as_text(day.get('date'))}#{_as_text(item.get('time'))}"


# 去掉 “午餐：” / “晚餐：” 这类前缀，只留活动主名用于匹配。
def _activity_core_name(activity: Any) -> str:
    return _as_text(activity).split("：")[-1].split(":")[-1].strip()


# 判断用户是否点名了这个活动：整名命中，或活动名中任一 >=3 字的连续片段出现在原话里。
# min_len=3 避免把 “公园” “老街” 这类 2 字通名误判为目标。
def _mentions_activity(user_message: str, activity: Any, min_len: int = 3) -> bool:
    name = _activity_core_name(activity)
    if not name or not user_message:
        return False
    if name in user_message:
        return True
    for size in range(len(name), min_len - 1, -1):
        for start in range(len(name) - size + 1):
            if name[start:start + size] in user_message:
                return True
    return False


# 优先级 1：用户点名了具体行程项。已发生/进行中的项不进作用域。
def _resolve_item_scope(state: TravelAgentState, user_message: str) -> Optional[Dict[str, Any]]:
    current_dt = _parse_current_datetime(get_current_time(state))
    keys: List[str] = []
    for day in get_daily_itinerary(state):
        if not isinstance(day, dict):
            continue
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            if _is_locked_item(day, item, current_dt):
                continue
            if _mentions_activity(user_message, item.get("activity")):
                keys.append(_item_scope_key(day, item))
    if not keys:
        return None
    return {"kind": "item", "target_dates": [], "target_days": [],
            "target_item_keys": keys, "instruction": user_message}


# 判断行程项是否落在本轮授权范围内。
def _in_replan_scope(day: Dict[str, Any], item: Dict[str, Any], scope: Optional[Dict[str, Any]]) -> bool:
    kind = (scope or {}).get("kind") or "all"
    if kind == "all":
        return True
    if kind == "day":
        if _as_text(day.get("date")) in set(scope.get("target_dates") or []):
            return True
        number = _day_number(day)
        return number is not None and number in set(scope.get("target_days") or [])
    if kind == "item":
        return _item_scope_key(day, item) in set(scope.get("target_item_keys") or [])
    return True


# 作用域覆盖的日期集合（item 作用域取被点名项所在日期）。
def _scope_dates(scope: Optional[Dict[str, Any]]) -> set:
    kind = (scope or {}).get("kind")
    if kind == "day":
        return set(scope.get("target_dates") or [])
    if kind == "item":
        return {key.split("#")[0] for key in (scope.get("target_item_keys") or []) if key}
    return set()


# 判断 LLM 生成的某一天是否落在授权范围内；范围外的整天直接忽略。
def _scope_allows_generated_day(day: Dict[str, Any], scope: Optional[Dict[str, Any]]) -> bool:
    if not scope or scope.get("kind") == "all":
        return True
    dates = _scope_dates(scope)
    if dates and _as_text(day.get("date")) in dates:
        return True
    numbers = set(scope.get("target_days") or [])
    number = _day_number(day)
    return bool(numbers) and number in numbers


# 中文数字转整数（支持 十一~十九）。
def _parse_cn_number(text: str) -> Optional[int]:
    value = text.strip()
    if value.isdigit():
        return int(value)
    if value in CN_DIGITS:
        return CN_DIGITS[value]
    if len(value) == 2 and value[0] == "十" and value[1] in CN_DIGITS:
        return 10 + CN_DIGITS[value[1]]
    return None


# 优先级 2：用户点名了日期而不是具体项。
# 判据：相对日词后 6 字内出现 “行程/安排/计划” 等对象标记词，才认作目标；
# 这样 “今天太累了” 里的 “今天” 是理由，“明天的行程” 里的 “明天” 才是目标。
def _resolve_day_scope(state: TravelAgentState, user_message: str) -> Optional[Dict[str, Any]]:
    current_dt = _parse_current_datetime(get_current_time(state))
    anchor = (current_dt or datetime.now()).date()
    dates: set = set()
    days: set = set()

    # a) 相对日：优先只认 “修饰行程对象” 的那个
    for word, offset in RELATIVE_DAY_OFFSETS.items():
        for match in re.finditer(re.escape(word), user_message):
            tail = user_message[match.end(): match.end() + 6]
            if any(marker in tail for marker in SCOPE_TARGET_MARKERS):
                dates.add((anchor + timedelta(days=offset)).isoformat())
    # b) 一个都没修饰行程对象时，退化为出现即命中
    if not dates:
        for word, offset in RELATIVE_DAY_OFFSETS.items():
            if word in user_message:
                dates.add((anchor + timedelta(days=offset)).isoformat())

    # c) 第N天 / 第三天
    for match in re.finditer(r"第\s*([0-9一二三四五六七八九十]{1,3})\s*天", user_message):
        number = _parse_cn_number(match.group(1))
        if number:
            days.add(number)

    # d) 8月22日 / 8月22号
    for match in re.finditer(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", user_message):
        try:
            dates.add(date(anchor.year, int(match.group(1)), int(match.group(2))).isoformat())
        except ValueError:
            continue

    if not dates and not days:
        return None
    return {"kind": "day", "target_dates": sorted(dates), "target_days": sorted(days),
            "target_item_keys": [], "instruction": user_message}


# 三级收敛入口：点名项 → 点名日期 → 全开放区。
def _resolve_replan_scope(state: TravelAgentState, user_message: str) -> Dict[str, Any]:
    text = (user_message or "").strip()
    if not text:
        return _scope_all()
    return (_resolve_item_scope(state, text)
            or _resolve_day_scope(state, text)
            or _scope_all(text))


# 构造 REPLAN 模式下只包含开放区的提示词上下文。
def _replan_payload(state: TravelAgentState, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    current_dt = _parse_current_datetime(get_current_time(state))
    locked_items = []        # 已发生/进行中：LLM 严禁触碰
    preserved_items = []     # 未来但本轮不在授权范围：LLM 只读不输出
    editable_itinerary = []  # 本轮授权可改：交给 LLM 重写
    for day in get_daily_itinerary(state):
        if not isinstance(day, dict):
            continue
        editable_day_items = []
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            if item.get("status") in LOCKED_STATUSES or _is_time_locked(day, item, current_dt):
                locked_items.append(_locked_item_summary(day, item))
            elif scope is not None and not _in_replan_scope(day, item, scope):
                preserved_items.append(_locked_item_summary(day, item))
            else:
                editable_day_items.append(deepcopy(item))

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
        "replan_scope": scope or _scope_all(),
        "locked_items": locked_items,
        "preserved_items": preserved_items,
        "editable_itinerary": editable_itinerary,
    }


# 获取最近一条用户消息，避免把 Supervisor 或其他 Agent 的回复当作用户需求。
def _latest_user_message(state: TravelAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", None) == "human":
            return message_content(message).strip()
    return ""


# 从用户当前输入中提取稳定偏好和明确的行程决策候选。
def _memory_candidates(user_message: str) -> List[tuple[str, str]]:
    text = user_message.strip()
    if not text:
        return []

    candidates = []
    if any(marker in text for marker in PREFERENCE_MARKERS):
        candidates.append(("preference", f"用户旅行偏好：{text}"))
    if any(marker in text for marker in ACTION_MARKERS):
        candidates.append(("action", f"用户行程决策：{text}"))
    return candidates


# 查询用户长期偏好；记忆服务不可用时不影响行程生成。
async def _retrieve_relevant_preferences(
    user_id: str,
    query: str,
) -> List[Dict[str, Any]]:
    if not user_id or not query.strip():
        return []
    try:
        from src.services.memory_manager import retrieve_memories

        return await retrieve_memories(
            user_id=user_id,
            query=query,
            memory_type="preference",
            top_k=5,
        )
    except Exception:
        logger.exception("Failed to retrieve user preferences")
        return []


# 查询历史行程调整，用于在首次规划时复用用户的实际选择。
async def _retrieve_relevant_action_logs(
    user_id: str,
    query: str,
) -> List[Dict[str, Any]]:
    if not user_id or not query.strip():
        return []
    try:
        from src.services.memory_manager import retrieve_memories

        return await retrieve_memories(
            user_id=user_id,
            query=query,
            memory_type="action",
            top_k=3,
        )
    except Exception:
        logger.exception("Failed to retrieve user action logs")
        return []


# 写入一条用户记忆；记忆服务异常时只记录日志。
async def _add_memory(
    user_id: str,
    text: str,
    memory_type: str = "preference",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    if not user_id or not text.strip():
        return ""
    try:
        from src.services.memory_manager import add_memory

        return await add_memory(
            user_id=user_id,
            text=text,
            memory_type=memory_type,
            metadata=dict(metadata or {}),
        )
    except Exception:
        logger.exception("Failed to store user memory")
        return ""


# 按用户、记忆类型和消息指纹避免同一进程内的重试重复写入。
async def _store_user_memory_candidates(
    state: TravelAgentState,
    user_message: str,
) -> None:
    user_id = str(state.get("user_id") or "").strip()
    if not user_id:
        return

    fingerprint = sha256(user_message.strip().encode("utf-8")).hexdigest()
    metadata = {
        "source": "itinerary_agent",
        "thread_id": state.get("thread_id"),
        "plan_mode": get_plan_mode(state),
        "message_fingerprint": fingerprint,
    }
    for memory_type, text in _memory_candidates(user_message):
        memory_key = f"{user_id}:{memory_type}:{fingerprint}"
        if memory_key in _STORED_MEMORY_KEYS:
            continue
        memory_id = await _add_memory(
            user_id=user_id,
            text=text,
            memory_type=memory_type,
            metadata=metadata,
        )
        if memory_id:
            _STORED_MEMORY_KEYS.add(memory_key)


# 将行程压缩成适合记录在操作日志中的文本，避免保存整个 State。
def _itinerary_summary(itinerary: List[Dict[str, Any]]) -> str:
    entries = []
    for day in itinerary:
        day_number = _as_text(day.get("day"), "?")
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            entries.append(
                f"D{day_number} {_as_text(item.get('time'), '未知时间')} "
                f"{_as_text(item.get('activity'), '未命名活动')}"
            )
    return "；".join(entries) or "无可用行程"


# 后台记录 REPLAN 的实际变更，日志失败不会影响当前请求。
async def _record_replan_action(
    state: TravelAgentState,
    original_itinerary: List[Dict[str, Any]],
    updated_itinerary: List[DayPlan],
    user_message: str,
) -> None:
    try:
        from src.services.memory_manager import log_user_action

        user_id = str(state.get("user_id") or "").strip()
        thread_id = str(state.get("thread_id") or "").strip()
        if not user_id or not thread_id:
            return
        await log_user_action(
            user_id=user_id,
            thread_id=thread_id,
            action_type="replan",
            original_content=_itinerary_summary(original_itinerary),
            new_content=_itinerary_summary(updated_itinerary),
            user_reason=user_message or "用户请求重新规划行程",
        )
    except Exception:
        logger.exception("Failed to record replan action")


def _schedule_replan_action_log(
    state: TravelAgentState,
    original_itinerary: List[Dict[str, Any]],
    updated_itinerary: List[DayPlan],
    user_message: str,
) -> None:
    try:
        task = asyncio.create_task(
            _record_replan_action(
                state,
                original_itinerary,
                updated_itinerary,
                user_message,
            )
        )
        task.add_done_callback(_consume_replan_log_task)
    except Exception:
        logger.exception("Failed to schedule replan action log")


def _consume_replan_log_task(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Replan action log task failed")


# 计算首日首个活动的最早起始时刻。
# 今天出发时取整到当前时刻(分钟非 0 则进位到下个整点)，不早于 09:00、不晚于 21:00；
# 非今天出发（含默认"明天"）固定返回 09:00。
def _first_day_start_hint(state: TravelAgentState) -> str:
    cur = _parse_current_datetime(get_current_time(state))
    start = get_start_date(state)
    if cur is None or cur.date() != start:
        return "09:00"
    hour = cur.hour if cur.minute == 0 else cur.hour + 1
    hour = max(9, min(hour, 21))
    return f"{hour:02d}:00"


# 构造预算自动削减模式的指令文案（含当前 total / 上限 / 超出额与明细）。
def _auto_reduce_instruction(state: TravelAgentState) -> Optional[str]:
    budget = state.get("draft_budget") or state.get("budget") or {}
    total = budget.get("total")
    max_allowed = state.get("budget_max_allowed")
    detail = budget.get("detail") or {}
    if total is None or max_allowed is None:
        return None
    try:
        total_f = float(total)
        max_allowed_f = float(max_allowed)
    except (TypeError, ValueError):
        return None
    over = round(total_f - max_allowed_f, 2)
    pct = round((total_f / max_allowed_f - 1) * 100, 1)
    parts = []
    for cat in ("tickets", "hotel", "transport", "food"):
        val = detail.get(cat)
        if isinstance(val, (int, float)) and val:
            parts.append(f"{cat}={val}元")
    detail_hint = "；".join(parts) if parts else "（无明细）"
    return (
        f"【预算自动削减模式】当前行程各项费用合计 {total_f} 元，超出预算上限 {max_allowed_f} 元"
        f"（超出 {over} 元，约 {pct}%）。预算明细：{detail_hint}。"
        f"请在保留每日午/晚餐结构与核心景点的前提下主动削减开销：优先取消或替换最昂贵的付费景点/体验；"
        f"降低住宿与市内交通等级（经济型酒店、公交/地铁替代打车）；压缩非必要购物/夜间消费。"
        f"目标：各项费用合计不超过 {max_allowed_f} 元。不要新增天数，不要删除午/晚餐。"
    )


# 将当前 State 压缩为适合提示词使用的上下文。
def _state_payload(
    state: TravelAgentState,
    relevant_preferences: Optional[List[Dict[str, Any]]] = None,
    relevant_action_logs: Optional[List[Dict[str, Any]]] = None,
    user_message: str = "",
    scope: Optional[Dict[str, Any]] = None,
    auto_reduce_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    mode = get_plan_mode(state)
    payload = {
        "plan_mode": mode,
        "mode": mode,
        "destination": get_destination(state),
        "start_date": get_start_date_text(state),
        "duration": get_duration(state),
        "current_time": get_current_time(state),
        "first_day_start_hint": _first_day_start_hint(state),
        "preferences": get_structured_preferences(state),
        # 4 项关键偏好抽为顶层字段，供 prompt 硬约束直接引用，避免 LLM 埋在 preferences dict 里靠自觉读取。
        "pace": get_pace(state),
        "interests": get_interests(state),
        "hotel_preference": get_hotel_preference(state),
        "lodging_mode": get_structured_preferences(state).get("lodging_mode") or "hotel",
        "local_transport": get_local_transport(state),
        "weather_info": state.get("weather_info"),
        "fetched_attractions": state.get("fetched_attractions"),
        "validation_report": state.get("validation_report"),
        "existing_itinerary": get_daily_itinerary(state),
        "relevant_preferences": relevant_preferences or [],
        "relevant_action_logs": relevant_action_logs or [],
        "user_decision": state.get("user_decision"),
        # 用户本轮原话：REPLAN 的最高优先级约束。旧实现只把它写进记忆再靠相似度捞回，
        # 极不可靠；这里直接进 payload，让 LLM 看到用户到底要改什么。
        "user_instruction": user_message,
        "budget_max_allowed": state.get("budget_max_allowed"),
        # 预算自动微调：非空时进入“削减模式”，让 LLM 基于现有行程砍最贵项/降档以不超上限。
        "auto_reduce_instruction": auto_reduce_instruction,
    }
    if mode == "replan":
        payload.update(_replan_payload(state, scope))
        payload.pop("existing_itinerary", None)
    return payload


# 构造要求 LLM 返回行程 JSON 的消息列表。
def _build_itinerary_messages(
    state: TravelAgentState,
    relevant_preferences: Optional[List[Dict[str, Any]]] = None,
    relevant_action_logs: Optional[List[Dict[str, Any]]] = None,
    user_message: str = "",
    scope: Optional[Dict[str, Any]] = None,
    auto_reduce_instruction: Optional[str] = None,
) -> list[Any]:
    system_prompt = """
你是 TravelMate 的 Itinerary Agent，只负责生成或调整 daily_itinerary，不生成预算明细（预算明细由 Budget Agent 统计），但须遵守 budget_max_allowed 上限约束。
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
          "activity": "景点、午餐、晚餐或可执行活动名称",
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
- PLAN 模式下每天必须覆盖午餐和晚餐时段：
  - 每天必须有 1 个午餐 item，time 必须在 11:30-13:30 之间，建议 time 为 "12:00"。
  - 每天必须有 1 个晚餐 item，time 必须在 17:30-19:30 之间，建议 time 为 "18:00"。
  - 午餐/晚餐必须作为独立 itinerary item 输出，不要只写在 tips 里。
  - 午餐/晚餐的 activity 使用“午餐：目的地特色餐/商圈名”或“晚餐：目的地特色餐/商圈名”。
  - 午餐/晚餐允许 image_url 为空，景点类 item 才必须有真实图片。
- PLAN 模式下每天建议安排 3-5 个 item，其中必须包含午餐和晚餐。
- REPLAN 模式下基于 editable_itinerary 重新规划开放区，locked_items 与 preserved_items 由后端原样合并，LLM 不得输出它们。
- user_instruction 是用户本轮原话，是 REPLAN 的最高优先级约束：用户点名要改的必须改，用户没提到的必须原样不动。
- 必须严格遵守 replan_scope（本轮授权范围）：
  - kind = "item"：只允许替换 editable_itinerary 里列出的这几项。替代项必须同一天、time 尽量保持原值（最多前后 30 分钟），数量与 editable_itinerary 一致，不得增删项。
  - kind = "day"：只允许重排 target_dates / target_days 指定的那几天，这几天可整体重写（增删改都允许），其它日期一律不输出。
  - kind = "all"：按 editable_itinerary 的全部开放区重新规划。
- preserved_items 是授权范围之外的未来行程：只能读取用于避免重复与衔接冲突，严禁输出、改写、删除或重排。
- 只输出被授权修改的那些天，未授权的天不要出现在 daily_itinerary 里。
- ItineraryItem.status 是硬边界：completed 和 ongoing 项严禁输出、改写、删除或重排。
- current_time 是逻辑锁：早于 current_time 的项目全部锁定，晚于或等于 current_time 的 upcoming 项才允许修改。
- first_day_start_hint 是首日首个活动的最早起始时刻：首日首个活动 time 不得早于 first_day_start_hint；若当天剩余时段不足以安排至少 2 项活动，则将首日整体顺延至次日并从 09:00 开始，后续天数相应后移。REPLAN 模式下此约束仅作用于被授权重排的首日。
- REPLAN 模式下不要重复输出已完成的行程；只返回未来开放区项目，且这些项目 status 必须是 upcoming。
- 优先利用 fetched_attractions、weather_info、preferences 和 relevant_preferences。
- budget_max_allowed（顶层字段，可能为 null）是用户设定的预算金额上限（元）。若非 null，生成行程时应主动自我约束：景点门票、交通、住宿、餐饮等各项开销合计不得超过该上限；预算紧张时优先保留核心景点、选用经济型交通与住宿、压缩非必要消费，并在对应 item 的 tips 中给出省钱提示。
- 若 payload 含 auto_reduce_instruction（非空字符串），则进入“预算削减模式”：必须基于现有行程（existing_itinerary / editable_itinerary，每项已带 cost 字段）削减开销，使各项费用合计不超过 budget_max_allowed；优先砍掉最昂贵的付费景点/体验、降低住宿与市内交通等级、压缩非必要购物/夜间消费，保留核心景点与每日午/晚餐结构；不要新增天数，不要删除午/晚餐。
- 偏好硬约束（必须遵守，不得遗漏）：
  - pace（顶层字段，intensive/relaxed）：intensive 每天安排 5-7 个 item（含午晚餐），景点密集、时间紧凑；relaxed 每天安排 3-4 个 item（含午晚餐），留白休息、避免早出晚归。
  - interests（顶层字段，可能含 history/culture/food/nature/shopping/art/nightlife）：景点选择必须优先匹配 interests 中的类别；含 history 或 culture 时每天至少 1 个历史/文化类景点；含 nature 时每天至少 1 个自然景观；含 food 时餐食突出目的地特色；含 shopping 时安排商圈；含 art 时安排美术馆/艺术区；含 nightlife 时安排夜间活动。interests 为空则按通用推荐（历史+美食为主）。
  - lodging_mode 为 home 时，不得安排酒店、民宿或住宿费用；每日从住处出发并返回住处。否则 hotel_preference（顶层字段，economy/mid/luxury）决定住宿选址与等级。
  - local_transport（顶层字段，可能含 metro/bus/taxi/self_driving/bike/walking）：市内交通方式必须落在 local_transport 列表内，不得主推未列出的方式；在景点间移动的 tips 标注主推交通（如“地铁2号线至XX站”）。含 metro 时市内优先地铁；不含 metro 不得主推地铁。local_transport 为空则按目的地通用推荐。
- 可参考 relevant_action_logs 中的历史调整进行个性化；但当前用户需求、preferences 和 user_decision 优先级更高。
- REPLAN 模式下，若 user_decision 存在，必须优先遵循其修改意图：
  - user_decision.action 为 "modify" 时，按 user_decision.hint 调整开放区景点/餐食/顺序（不得触碰 locked_items 与 completed/ongoing 项）；
  - user_decision.action 为 "accept" 时，尽量保持现有开放区结构，仅做必要优化；
  - user_decision.note 若非空，作为补充约束一并考虑。
- 不要返回 budget 字段。
""".strip()
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=json.dumps(
                _state_payload(
                    state,
                    relevant_preferences,
                    relevant_action_logs,
                    user_message,
                    scope,
                    auto_reduce_instruction,
                ),
                ensure_ascii=False,
            )
        ),
    ]


# 将任意值转换成字符串，缺失时使用默认值。
def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _image_url_for_activity(activity: str, fetched_attractions: Any) -> str:
    if not isinstance(fetched_attractions, list):
        return ""
    for attraction in fetched_attractions:
        if not isinstance(attraction, dict):
            continue
        name = _as_text(attraction.get("name"))
        image_url = _as_text(attraction.get("image_url"))
        if name and image_url and name in activity:
            return image_url
    return ""


def _requires_activity_image_url(item: Dict[str, Any]) -> bool:
    """
    判断行程项是否需要真实图片 URL。
    规则：
    1. 如果 activity 为空，则不需要图片。
    2. 如果 activity 包含交通/移动相关的关键词，则不需要图片。
    3. 如果 activity 包含餐饮相关的关键词，则不需要图片。
    4. 如果 activity 在午餐/晚餐时间段内，则不需要图片。
    """
    activity = _as_text(item.get("activity"))
    if not activity:
        return True

    # 1. 显式过滤交通/移动相关
    if any(marker in activity for marker in ("机场", "车站", "地铁", "高铁", "火车", "打车")):
        return False

    # 2. 增加常见的餐饮标识（包含“午餐”、“晚餐”、“用餐”等）
    meal_markers = ("餐", "饭", "咖啡", "茶", "小吃", "午餐", "晚餐", "早餐", "美食", "料理")
    if any(marker in activity for marker in meal_markers):
        return False

    # 3. 兜底的时间段逻辑(11:30~13:30, 17:30~19:30) + 景区/公园/博物馆等关键词
    minutes = parse_time_to_minutes(item.get("time"))
    is_meal_time = (11 * 60 + 30 <= minutes <= 13 * 60 + 30) or (17 * 60 + 30 <= minutes <= 19 * 60 + 30)
    is_clear_attraction = any(marker in activity for marker in ("景区", "公园", "博物", "故宫", "寺", "馆", "山"))

    return not (is_meal_time and not is_clear_attraction)


# 精确查询高德并获取活动对应的真实图片 URL。
async def _fetch_activity_image_url(destination: str, activity: str) -> str:
    from src.services.map import fetch_activity_image_url

    return await fetch_activity_image_url(destination, activity)

@trace_span(
    "agents.itinerary.ensure_itinerary_image_urls",
    span_type="function",
)
async def _ensure_itinerary_image_urls(
    itinerary: List[DayPlan],
    state: TravelAgentState,
) -> List[DayPlan]:
    destination = get_destination(state)
    for day in itinerary:
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            if _as_text(item.get("image_url")):
                continue
            activity = _as_text(item.get("activity"), "待定活动")
            if not _requires_activity_image_url(item):
                item["image_url"] = ""
                continue
            image_url = await _fetch_activity_image_url(destination, activity)
            if not image_url:
            # 如果是餐饮/交通等非核心景点，查不到图片不抛异常，直接留空
              if not _requires_activity_image_url(item):
                item["image_url"] = ""
            item["image_url"] = image_url
    return itinerary


# 规范化单个行程项，保证符合 ItineraryItem 字段要求。
@trace_span(
    "agents.itinerary.normalize_itinerary",
    span_type="function",
)
def _normalize_item(raw: Any, fetched_attractions: Any = None) -> ItineraryItem:
    item = ensure_dict(raw, "itinerary item")
    status = _as_text(item.get("status"), "upcoming")
    if status not in {"completed", "ongoing", "upcoming"}:
        status = "upcoming"

    activity = _as_text(item.get("activity"), "待定活动")
    image_url = _as_text(item.get("image_url"))
    if not image_url:
        image_url = _image_url_for_activity(activity, fetched_attractions)

    return {
        "time": _as_text(item.get("time"), "09:00"),
        "activity": activity,
        "duration": _as_text(item.get("duration"), "1h"),
        "address": _as_text(item.get("address"), ""),
        "image_url": image_url,
        "status": status,
        "tips": _as_text(item.get("tips"), ""),
        # 定价字段：若上游/LLM 已给则保留，否则由 cost_enrich 阶段补齐
        "cost": item.get("cost"),
        "cost_category": item.get("cost_category"),
        "poi_ref": item.get("poi_ref"),
        "location": item.get("location"),
        "leg_transport_cost": item.get("leg_transport_cost"),
    }


# 规范化单日行程，补齐 day、date 和 items。
def _normalize_day(raw: Any, fallback_day: int, fallback_date: str, fetched_attractions: Any = None) -> DayPlan:
    day = ensure_dict(raw, "day plan")
    items = [_normalize_item(item, fetched_attractions) for item in ensure_list(day.get("items", []), "items")]
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
        # 按 LLM 给的 day 字段推 fallback_date，而非 enumerate 下标；
        # 否则 LLM 只返回 Day2 时它是列表首项，下标会把它当成 Day1 而串天。
        day_hint = as_positive_int(ensure_dict(raw_day, "day plan").get("day"), index) or index
        fallback_date = (start + timedelta(days=day_hint - 1)).isoformat()
        normalized.append(_normalize_day(raw_day, day_hint, fallback_date, state.get("fetched_attractions")))

    if not normalized:
        raise ValueError("daily_itinerary must not be empty")
    return normalized


# 硬兜底：当首日首个活动早于“首日起始下限”时，把整段行程顺延一天。
# 这是方案3 prompt 软约束（_first_day_start_hint 规则）的兜底——LLM 可能不守规则仍输出
# 过早的首日项，导致该项被 _apply_time_based_status 事后标为 completed（过期活动）。
# 此处不依赖 LLM：只要首日首项 time < 下限，就整体 date+1、day 编号保持 1..N（仅日期后移，
# 避免出现“Day 2 起始”的歧义标签），物理上让首日落到未过期区间。仅作用于 PLAN 初次生成。
def _enforce_first_day_start(
    itinerary: List[Dict[str, Any]],
    state: TravelAgentState,
) -> List[Dict[str, Any]]:
    if not itinerary:
        return itinerary
    first_day = itinerary[0]
    items = first_day.get("items") or []
    if not items:
        return itinerary
    hint_minutes = parse_time_to_minutes(_first_day_start_hint(state))
    first_item_minutes = parse_time_to_minutes(items[0].get("time"))
    if hint_minutes < 0 or first_item_minutes < 0:
        return itinerary
    # 首日首项未早于下限，无需顺延（例如默认明天、或今天但 LLM 已遵守下限）
    if first_item_minutes >= hint_minutes:
        return itinerary
    # 顺延一天：所有 day 的 date +1，day 编号保持 1..N
    start = get_start_date(state)
    new_start = start + timedelta(days=1)
    for index, day in enumerate(itinerary):
        day["day"] = index + 1
        day["date"] = (new_start + timedelta(days=index)).isoformat()
    logger.info(
        "Enforced first-day start: shifted itinerary by +1 day (hint=%s, first_item=%s)",
        _first_day_start_hint(state),
        items[0].get("time"),
    )
    return itinerary


# PLAN 初次生成的硬边界：日期以业务规则解析出的 start_date 为准，所有项目都是未来态；
# 若今天仍可规划，则移除首日起始下限之前的过期项目，而不是将其伪装成 completed。
def _enforce_initial_plan_constraints(
    itinerary: List[Dict[str, Any]],
    state: TravelAgentState,
) -> List[Dict[str, Any]]:
    if not itinerary:
        return itinerary

    start = get_start_date(state)
    original_first_items = deepcopy(itinerary[0].get("items") or [])
    for index, day in enumerate(itinerary):
        day["day"] = index + 1
        day["date"] = (start + timedelta(days=index)).isoformat()
        items = [item for item in (day.get("items") or []) if isinstance(item, dict)]
        for item in items:
            item["status"] = "upcoming"
        day["items"] = _sort_items_by_time(items)

    current_dt = _parse_current_datetime(get_current_time(state))
    if get_start_date_text(state) or current_dt is None or start != current_dt.date():
        return itinerary

    hint_minutes = parse_time_to_minutes(_first_day_start_hint(state))
    itinerary[0]["items"] = [
        item
        for item in itinerary[0]["items"]
        if parse_time_to_minutes(item.get("time")) >= hint_minutes
    ]
    if itinerary[0]["items"]:
        return itinerary

    # LLM 若把首日全部排在过去，保留项目内容并整体从明天 09:00 开始，避免空 Day 1。
    new_start = current_dt.date() + timedelta(days=1)
    for item in original_first_items:
        item["status"] = "upcoming"
    itinerary[0]["items"] = _sort_items_by_time(original_first_items)
    for index, day in enumerate(itinerary):
        day["date"] = (new_start + timedelta(days=index)).isoformat()
    return itinerary


# 按 current_time 把"默认 upcoming 且已过去"的行程项推导为 completed。
# 仅覆写 LLM / 规范化留下的默认 upcoming，不触碰显式设置的 completed/ongoing（硬边界）。
def _apply_time_based_status(itinerary: Any, current_dt: Optional[datetime]) -> None:
    if not current_dt:
        return
    for day in ensure_list(itinerary, "itinerary"):
        if not isinstance(day, dict):
            continue
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            if item.get("status") != "upcoming":
                continue
            item_dt = _item_datetime(day, item)
            if item_dt and item_dt < current_dt:
                item["status"] = "completed"


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
@trace_span(
    "agents.itinerary.merge_replan_itinerary",
    span_type="function",
)
def _merge_replan_itinerary(
    llm_itinerary: List[DayPlan],
    state: TravelAgentState,
    scope: Optional[Dict[str, Any]] = None,
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
        # 范围外的天：即使 LLM 多输出了也不采纳，退回“保留原样”分支
        if generated_day is not None and not _scope_allows_generated_day(
            {"day": day_number, "date": date_text}, scope
        ):
            generated_day = None
        locked_items = [
            deepcopy(item)
            for item in ensure_list((existing_day or {}).get("items", []), "items")
            if isinstance(item, dict) and _is_locked_item(existing_day or {}, item, current_dt, scope)
        ]
        locked_refs = [
            _locked_item_summary({"day": day_number, "date": date_text}, item)
            for item in locked_items
        ]

        if generated_day is None:
            editable_items = [
                deepcopy(item)
                for item in ensure_list((existing_day or {}).get("items", []), "items")
                if isinstance(item, dict) and not _is_locked_item(existing_day or {}, item, current_dt, scope)
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
def _has_replan_editable_scope(
    state: TravelAgentState,
    scope: Optional[Dict[str, Any]] = None,
) -> bool:
    current_dt = _parse_current_datetime(get_current_time(state))
    return any(
        isinstance(day, dict) and _has_editable_items(day, current_dt, scope)
        for day in get_daily_itinerary(state)
    )


# 调用 LLM 生成行程，并将结果写回 State。
@trace_span(
    "agents.itinerary.itinerary_agent_node",
    span_type="workflow",
)
async def itinerary_agent_node(state: TravelAgentState) -> Dict[str, Any]:
    mode = get_plan_mode(state)
    logger.info("Running LLM itinerary node, mode=%s", mode)
    user_message = _latest_user_message(state)
    # 预算自动微调：本轮由 validator 触发，要求 LLM 自行削减行程以不超上限。
    auto_reduce = bool(state.get("auto_reduce_budget"))
    # REPLAN 作用域：把“用户本轮到底要改什么”收敛成结构，约束 LLM 只改授权部分。
    # 预算自动微调时强制全开放区（_scope_all），让 LLM 可在未来可改天内自由削减。
    if auto_reduce and mode == "replan":
        scope = _scope_all()
    else:
        scope = _resolve_replan_scope(state, user_message) if mode == "replan" else None
    auto_reduce_instruction = _auto_reduce_instruction(state) if auto_reduce else None
    await _store_user_memory_candidates(state, user_message)

    if mode == "replan" and get_daily_itinerary(state) and not _has_replan_editable_scope(state, scope):
        current_dt = _parse_current_datetime(get_current_time(state))
        draft_itinerary = deepcopy(get_daily_itinerary(state))
        _apply_time_based_status(draft_itinerary, current_dt)
        return {
            "draft_daily_itinerary": draft_itinerary,
            "plan_mode": mode,
            "current_mode": mode,
            "replan_scope": scope,
            "validation_attempts": 0,
        }

    user_id = str(state.get("user_id") or "")
    # PLAN 与 REPLAN 均检索偏好与历史操作日志。
    # 原先 REPLAN 不检索 action_logs，导致用户过往修改习惯在最该延续的“调整行程”场景反而缺失。
    relevant_preferences, relevant_action_logs = await asyncio.gather(
        _retrieve_relevant_preferences(user_id, user_message),
        _retrieve_relevant_action_logs(user_id, user_message),
    )

    llm = get_itinerary_llm()
    response = await call_llm(
        llm,
        _build_itinerary_messages(
            state,
            relevant_preferences,
            relevant_action_logs,
            user_message,
            scope,
            auto_reduce_instruction,
        ),
    )
    parsed = ensure_dict(extract_json(message_content(response)), "itinerary response")
    itinerary = _normalize_itinerary(parsed, state)
    if mode == "replan" and get_daily_itinerary(state):
        original_itinerary = deepcopy(get_daily_itinerary(state))
        itinerary = _merge_replan_itinerary(itinerary, state, scope)
        itinerary = await _ensure_itinerary_image_urls(itinerary, state)
        itinerary = await enrich_itinerary_costs(itinerary, state)
        _schedule_replan_action_log(
            state,
            original_itinerary,
            itinerary,
            user_message,
        )
        return {
            "draft_daily_itinerary": itinerary,
            "plan_mode": mode,
            "current_mode": mode,
            "replan_scope": scope,
            "validation_attempts": 0,
        }

    itinerary = await _ensure_itinerary_image_urls(itinerary, state)
    itinerary = await enrich_itinerary_costs(itinerary, state)
    itinerary = _enforce_initial_plan_constraints(itinerary, state)
    return {
        "draft_daily_itinerary": itinerary,
        "plan_mode": mode,
        "current_mode": mode,
        "replan_scope": None,
        "validation_attempts": 0,
    }
