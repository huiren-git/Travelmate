"""Budget Agent: 使用 LLM 生成预算。"""

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import BudgetDetail, TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, ensure_list, extract_json, message_content
from src.utils.state_utils import (
    get_budget_level,
    get_daily_itinerary,
    get_destination,
    get_duration,
    get_origin,
    get_start_date_text,
    get_structured_preferences,
    get_travelers,
)

logger = logging.getLogger("travelmate.agents.budget")


# 获取预算 Agent 使用的 LLM 实例。
def get_budget_llm():
    from src.agents.base import get_llm

    return get_llm(temperature=0.2)


# 将当前 State 压缩为预算生成所需的上下文。
def _state_payload(state: TravelAgentState) -> Dict[str, Any]:
    return {
        "destination": get_destination(state),
        "origin": get_origin(state),
        "start_date": get_start_date_text(state),
        "duration": get_duration(state),
        "travelers": get_travelers(state),
        "budget_level": get_budget_level(state),
        "preferences": get_structured_preferences(state),
        "daily_itinerary": get_daily_itinerary(state),
        "weather_info": state.get("weather_info"),
        "fetched_attractions": state.get("fetched_attractions"),
    }


# 构造要求 LLM 返回预算 JSON 的消息列表。
def _build_budget_messages(state: TravelAgentState) -> list[Any]:
    system_prompt = """
你是 TravelMate 的 Budget Agent，只负责生成 budget，不要生成 daily_itinerary。
请只返回 JSON，不要返回 Markdown 或额外解释。
JSON schema:
{
  "budget": {
    "level": "economy | mid | luxury",
    "total": 2800.0,
    "detail": {
      "transport": 600.0,
      "hotel": 1200.0,
      "food": 650.0,
      "tickets": 350.0
    },
    "saving_tips": ["省钱建议"]
  }
}
规则：
- total 必须等于 detail 中所有分类金额之和。
- 根据 travelers、duration、budget_level 和 daily_itinerary 估算费用。
- 如果没有 daily_itinerary，则根据目的地、天数和偏好直接估算。
- 不要返回 daily_itinerary 字段。
""".strip()
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(_state_payload(state), ensure_ascii=False)),
    ]


# 将任意数值转换为非负浮点数。
def _as_non_negative_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


# 将任意值转换成字符串，缺失时使用默认值。
def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


# 规范化预算明细，保证四个核心分类都存在。
def _normalize_detail(raw: Any) -> Dict[str, float]:
    detail = ensure_dict(raw or {}, "budget.detail")
    return {
        "transport": _as_non_negative_float(detail.get("transport")),
        "hotel": _as_non_negative_float(detail.get("hotel")),
        "food": _as_non_negative_float(detail.get("food")),
        "tickets": _as_non_negative_float(detail.get("tickets")),
    }


# 规范化预算对象，保证符合 BudgetDetail 字段要求。
def _normalize_budget(raw: Dict[str, Any], state: TravelAgentState) -> BudgetDetail:
    budget = ensure_dict(raw.get("budget"), "budget")
    level = _as_text(budget.get("level"), get_budget_level(state))
    if level not in {"economy", "mid", "luxury"}:
        level = get_budget_level(state)

    detail = _normalize_detail(budget.get("detail"))
    detail_sum = sum(detail.values())
    total = _as_non_negative_float(budget.get("total"), detail_sum)
    if abs(total - detail_sum) > 0.01:
        total = detail_sum

    tips = [_as_text(tip) for tip in ensure_list(budget.get("saving_tips", []), "saving_tips")]
    return {
        "level": level,
        "total": float(total),
        "detail": detail,
        "saving_tips": [tip for tip in tips if tip],
    }


# 调用 LLM 生成预算，并将结果写回 State。
async def budget_agent_node(state: TravelAgentState) -> Dict[str, Any]:
    logger.info(
        "Running LLM budget node, level=%s, duration=%s, travelers=%s",
        get_budget_level(state),
        get_duration(state),
        get_travelers(state),
    )

    llm = get_budget_llm()
    response = await call_llm(llm, _build_budget_messages(state))
    parsed = ensure_dict(extract_json(message_content(response)), "budget response")
    budget = _normalize_budget(parsed, state)

    return {"budget": budget}
