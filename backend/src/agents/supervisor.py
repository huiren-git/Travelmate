"""Supervisor node: use an LLM to classify intent and choose the next graph node."""

import json
import logging
import re
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.core.tracing import trace_span
from src.graph.state import TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, extract_json, message_content
from src.utils.state_utils import (
    as_positive_int,
    get_current_mode,
    get_current_time,
    get_destination,
    get_optional_duration,
    get_origin,
    get_plan_mode,
    get_start_date_text,
    get_travelers,
    has_budget,
    has_daily_itinerary,
    normalized_text,
)

logger = logging.getLogger("travelmate.agents.supervisor")

ALLOWED_NEXT_NODES = {"itinerary_agent", "budget_agent", "__end__"}
ALLOWED_MODES = {"plan", "replan"}
ALLOWED_INTENTS = {"plan", "consult", "update_preferences", "replan"}


# 获取 Supervisor 使用的 LLM 实例。
def get_supervisor_llm():
    from src.agents.base import get_llm

    return get_llm(temperature=0.0)


# 将当前 State 和用户消息压缩为路由判断上下文。
def _state_summary(state: TravelAgentState, user_message: str) -> str:
    return json.dumps(
        {
            "user_message": user_message,
            "destination": get_destination(state, default=None),
            "origin": get_origin(state),
            "start_date": get_start_date_text(state),
            "duration": get_optional_duration(state),
            "plan_mode": get_plan_mode(state),
            "current_mode": get_current_mode(state),
            "current_time": get_current_time(state),
            "has_daily_itinerary": has_daily_itinerary(state),
            "has_budget": has_budget(state),
        },
        ensure_ascii=False,
    )


# 构造要求 LLM 返回路由决策 JSON 的消息列表。
def _build_routing_messages(state: TravelAgentState, user_message: str) -> list[Any]:
    system_prompt = """
你是 TravelMate 的 Supervisor Agent，只负责意图识别和路由。
可用下游节点：
- itinerary_agent：生成或修改行程。用户要规划路线、安排景点、调整行程、重规划时选择它。
- budget_agent：估算或修改预算。用户重点询问预算、花费、费用、价格、省钱建议时选择它。
- __end__：信息不足，需要先追问用户，或无法处理当前请求时选择它。

当前只输出 JSON，不要输出 Markdown，不要解释。
JSON schema:
{
  "next_node": "itinerary_agent | budget_agent | __end__",
  "intent": "plan | consult | update_preferences | replan",
  "plan_mode": "plan | replan",
  "destination": "如果从用户消息中识别出目的地则填写，否则 null",
  "duration": "如果从用户消息中识别出旅行天数则填写整数，否则 null",
  "budget_max": "如果用户消息中明确提到预算金额上限则填写整数元，否则 null",
  "budget_scope": "total | per_person，预算金额是总额还是人均，默认 total",
  "origin": "如果用户更新了出发地则填写，否则 null",
  "travelers": "如果用户更新了人数则填写正整数，否则 null",
  "preference_updates": "用户明确更新的预算等级、节奏、兴趣、交通或住宿偏好对象；住家里、无需酒店或无需住宿时写 {\"lodging_mode\":\"home\"}，否则 {}",
  "reply": "当 next_node 为 __end__ 时给用户的追问或说明，否则 null",
  "reason": "一句话说明路由原因"
}

规则：
- 必须输出 intent 和 plan_mode 字段，不要输出 current_mode 字段。
- consult：仅回答天气准备、注意事项、当地规则等旅行问题。next_node 必须为 __end__，reply 必须是可直接给用户的答案；不得修改行程或偏好。
- update_preferences：用户更新出发地、人数、预算或偏好。若已有 daily_itinerary 且更新影响交通或预算，next_node 用 budget_agent；否则用 __end__ 并在 reply 确认已更新。不得路由到 itinerary_agent，也不得修改每日景点安排。
- replan：仅当用户明确要求修改、替换或删除某一天或某个景点时使用。范围未明确时 next_node 必须为 __end__，reply 追问要调整哪一天或哪个景点；禁止默认全量改写。
- 如果用户已有目的地和天数，或消息中能识别出目的地和天数，且主要需求是行程规划，路由到 itinerary_agent。
- 如果用户主要询问预算/费用，即使还没有完整行程，也可以路由到 budget_agent。
- 如果用户说修改、调整、不想去、取消、太累、换一个、别去、不去、删除等，并且已有行程上下文，plan_mode 用 replan。
- 如果缺少行程规划所需的目的地或天数，next_node 用 __end__，reply 里追问缺失信息。
""".strip()
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=_state_summary(state, user_message)),
    ]


# 判断用户消息是否明显是在修改已有行程。
def _looks_like_replan_request(state: TravelAgentState, user_message: str) -> bool:
    if not has_daily_itinerary(state):
        return False
    keywords = (
        "修改",
        "调整",
        "重排",
        "重新安排",
        "取消",
        "删除",
        "不想去",
        "不去",
        "别去",
        "换",
        "改成",
        "太累",
        "轻松",
    )
    return any(keyword in user_message for keyword in keywords)


def _has_explicit_replan_scope(state: TravelAgentState, user_message: str) -> bool:
    """Require a day/date/activity target before allowing itinerary mutation."""
    if re.search(r"(?:第\s*\d+\s*天|day\s*\d+|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|今天|明天|后天|上午|下午|晚上)", user_message, re.IGNORECASE):
        return True
    for day in state.get("daily_itinerary") or []:
        for item in day.get("items") or []:
            activity = str(item.get("activity") or "").strip()
            if activity and activity in user_message:
                return True
    return False


# 规范化 LLM 返回的路由决策，避免非法节点或模式进入图。
def _normalize_decision(raw: Dict[str, Any], state: TravelAgentState, user_message: str) -> Dict[str, Any]:
    next_node = raw.get("next_node")
    if next_node not in ALLOWED_NEXT_NODES:
        next_node = "__end__"

    intent = raw.get("intent")
    if intent not in ALLOWED_INTENTS:
        intent = "replan" if _looks_like_replan_request(state, user_message) else "plan"

    plan_mode = raw.get("plan_mode") or raw.get("current_mode")
    if plan_mode not in ALLOWED_MODES:
        plan_mode = "plan"
    if intent == "replan" or (next_node == "itinerary_agent" and _looks_like_replan_request(state, user_message)):
        intent = "replan"
        plan_mode = "replan"

    if intent == "consult":
        next_node = "__end__"
    elif intent == "update_preferences":
        next_node = "budget_agent" if has_daily_itinerary(state) else "__end__"
    elif intent == "replan" and not _has_explicit_replan_scope(state, user_message):
        next_node = "__end__"

    budget_max = as_positive_int(raw.get("budget_max"), None)
    budget_scope = (
        raw.get("budget_scope")
        if raw.get("budget_scope") in {"total", "per_person"}
        else "total"
    )
    # 人均预算折算为总额：乘以出行人数
    if budget_max and budget_scope == "per_person":
        budget_max = budget_max * max(1, get_travelers(state))

    return {
        "intent": intent,
        "next_node": next_node,
        "plan_mode": plan_mode,
        "current_mode": plan_mode,
        "destination": normalized_text(raw.get("destination"), None),
        "duration": as_positive_int(raw.get("duration"), None),
        "budget_max": budget_max,
        "origin": normalized_text(raw.get("origin"), None),
        "travelers": as_positive_int(raw.get("travelers"), None),
        "preference_updates": raw.get("preference_updates") if isinstance(raw.get("preference_updates"), dict) else {},
        "reply": normalized_text(raw.get("reply"), None),
        "reason": raw.get("reason"),
    }


# 检查进入行程规划分支前还缺少哪些必要字段。
def _missing_trip_fields(state: TravelAgentState, decision: Dict[str, Any]) -> list[str]:
    destination = decision.get("destination") or get_destination(state, default=None)
    duration = decision.get("duration") or get_optional_duration(state)
    missing = []
    if not destination:
        missing.append("目的地")
    if not duration:
        missing.append("旅行天数")
    return missing


# 构造信息不足时返回给用户的追问消息。
def _ask_for_missing_fields(missing: list[str], reply: Optional[str] = None, intent: str = "plan") -> Dict[str, Any]:
    if reply:
        content = reply
    elif missing:
        content = f"好的，我还需要确认：{'、'.join(missing)}。"
    else:
        content = "我还需要更多信息，才能继续帮你规划。"
    return {
        "messages": [AIMessage(content=content)],
        "intent": intent,
        "next_node": "__end__",
        "is_finished": True,
    }


# 调用 LLM 识别用户意图，并把路由字段写回 State。
@trace_span(
    "agents.supervisor.supervisor_node",
    span_type="workflow",
)
async def supervisor_node(state: TravelAgentState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    if not messages:
        logger.warning("No messages found; ending workflow.")
        return {"next_node": "__end__", "is_finished": True}

    user_message = message_content(messages[-1])
    logger.info("Supervisor routing message: %s", user_message[:80])

    llm = get_supervisor_llm()
    response = await call_llm(llm, _build_routing_messages(state, user_message))
    decision = _normalize_decision(
        ensure_dict(extract_json(message_content(response)), "routing response"),
        state,
        user_message,
    )

    logger.info("Supervisor LLM decision: %s", decision)

    if decision["intent"] == "consult":
        return _ask_for_missing_fields(
            [],
            decision.get("reply") or "我可以帮你解答旅行准备、天气和当地规则方面的问题。",
            "consult",
        )

    if decision["intent"] == "replan" and decision["next_node"] == "__end__":
        return _ask_for_missing_fields(
            [],
            "请告诉我想调整哪一天，或要修改、替换、删除哪个景点。",
            "replan",
        )

    if decision["intent"] == "update_preferences" and decision["next_node"] == "__end__":
        update = _preference_state_update(state, decision)
        return {
            **update,
            "messages": [AIMessage(content=decision.get("reply") or "出发信息和偏好已更新，现有每日景点安排保持不变。")],
            "next_node": "__end__",
            "is_finished": True,
        }

    if decision["next_node"] == "itinerary_agent" and decision["plan_mode"] == "plan":
        missing = _missing_trip_fields(state, decision)
        if missing:
            return _ask_for_missing_fields(missing, decision.get("reply"), decision["intent"])

    if decision["next_node"] == "__end__":
        return _ask_for_missing_fields(_missing_trip_fields(state, decision), decision.get("reply"), decision["intent"])

    update: Dict[str, Any] = {
        "intent": decision["intent"],
        "next_node": decision["next_node"],
        "plan_mode": decision["plan_mode"],
        "current_mode": decision["plan_mode"],
        "is_finished": False,
    }
    if decision["intent"] == "update_preferences":
        update.update(_preference_state_update(state, decision))

    if decision.get("destination") and not get_destination(state, default=None):
        update["destination"] = decision["destination"]
    if decision.get("duration") and not get_optional_duration(state):
        update["duration"] = decision["duration"]
    # 文本预算优先于表单 budget_level：supervisor 抽取到金额则直接写入上限；
    # 与旧值不同（含从无到有）时置 budget_dirty，让 replan 也重跑 budget_agent 重翻 total。
    if decision.get("budget_max"):
        new_max = decision["budget_max"]
        update["budget_max_allowed"] = new_max
        prev_max = state.get("budget_max_allowed")
        if prev_max is None or float(prev_max) != float(new_max):
            update["budget_dirty"] = True

    return update


def _preference_state_update(state: TravelAgentState, decision: Dict[str, Any]) -> Dict[str, Any]:
    """Merge explicitly changed preferences without touching the daily itinerary."""
    preferences = dict(state.get("structured_preferences") or {})
    preferences.update(decision.get("preference_updates") or {})
    if decision.get("travelers"):
        preferences["travelers"] = decision["travelers"]
    update: Dict[str, Any] = {"intent": "update_preferences", "structured_preferences": preferences}
    if decision.get("origin"):
        update["origin"] = decision["origin"]
    if decision.get("budget_max"):
        update["budget_max_allowed"] = decision["budget_max"]
        update["budget_dirty"] = state.get("budget_max_allowed") != decision["budget_max"]
    return update
