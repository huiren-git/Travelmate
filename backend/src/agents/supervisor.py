"""Supervisor node: use an LLM to classify intent and choose the next graph node."""

import json
import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

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
    get_structured_preferences,
    has_budget,
    has_daily_itinerary,
    normalized_text,
)

logger = logging.getLogger("travelmate.agents.supervisor")

ALLOWED_NEXT_NODES = {"itinerary_agent", "budget_agent", "__end__"}
ALLOWED_MODES = {"plan", "replan"}


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
            "structured_preferences": get_structured_preferences(state),
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
  "plan_mode": "plan | replan",
  "destination": "如果从用户消息中识别出目的地则填写，否则 null",
  "duration": "如果从用户消息中识别出旅行天数则填写整数，否则 null",
  "reply": "当 next_node 为 __end__ 时给用户的追问或说明，否则 null",
  "reason": "一句话说明路由原因"
}

规则：
- 必须输出 plan_mode 字段，不要输出 current_mode 字段。
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


# 规范化 LLM 返回的路由决策，避免非法节点或模式进入图。
def _normalize_decision(raw: Dict[str, Any], state: TravelAgentState, user_message: str) -> Dict[str, Any]:
    next_node = raw.get("next_node")
    if next_node not in ALLOWED_NEXT_NODES:
        next_node = "__end__"

    plan_mode = raw.get("plan_mode") or raw.get("current_mode")
    if plan_mode not in ALLOWED_MODES:
        plan_mode = "plan"
    if next_node == "itinerary_agent" and _looks_like_replan_request(state, user_message):
        plan_mode = "replan"

    return {
        "next_node": next_node,
        "plan_mode": plan_mode,
        "current_mode": plan_mode,
        "destination": normalized_text(raw.get("destination"), None),
        "duration": as_positive_int(raw.get("duration"), None),
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
def _ask_for_missing_fields(missing: list[str], reply: Optional[str] = None) -> Dict[str, Any]:
    if reply:
        content = reply
    elif missing:
        content = f"好的，我还需要确认：{'、'.join(missing)}。"
    else:
        content = "我还需要更多信息，才能继续帮你规划。"
    return {
        "messages": [AIMessage(content=content)],
        "next_node": "__end__",
        "is_finished": True,
    }


# 调用 LLM 识别用户意图，并把路由字段写回 State。
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

    if decision["next_node"] == "itinerary_agent" and decision["plan_mode"] == "plan":
        missing = _missing_trip_fields(state, decision)
        if missing:
            return _ask_for_missing_fields(missing, decision.get("reply"))

    if decision["next_node"] == "__end__":
        return _ask_for_missing_fields(_missing_trip_fields(state, decision), decision.get("reply"))

    update: Dict[str, Any] = {
        "next_node": decision["next_node"],
        "plan_mode": decision["plan_mode"],
        "current_mode": decision["plan_mode"],
        "is_finished": False,
    }

    if decision.get("destination") and not get_destination(state, default=None):
        update["destination"] = decision["destination"]
    if decision.get("duration") and not get_optional_duration(state):
        update["duration"] = decision["duration"]

    return update
