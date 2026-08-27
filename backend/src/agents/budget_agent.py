"""Budget Agent: 使用 LLM 生成预算。"""

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from src.core.tracing import trace_span
from src.graph.state import TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, ensure_list, extract_json, message_content
from src.utils.state_utils import (
    get_budget_level,
    get_daily_itinerary,
    get_draft_daily_itinerary,
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
        "daily_itinerary": get_draft_daily_itinerary(state) or get_daily_itinerary(state),
        "weather_info": state.get("weather_info"),
        "fetched_attractions": state.get("fetched_attractions"),
    }


# 构造要求 LLM 返回预算 JSON 的消息列表。
def _build_budget_messages(state: TravelAgentState) -> list[Any]:
    system_prompt = """
你是 TravelMate 的 Budget Agent。daily_itinerary 各项费用已由后端根据 POI 真实单价、交通距离与属性估算汇总得出，
你不需要计算 total / detail。请只返回 JSON，不要返回 Markdown 或额外解释。
JSON schema:
{
  "budget": {
    "level": "economy | mid | luxury",
    "saving_tips": ["省钱建议"]
  }
}
规则：
- level 根据 travelers、duration、budget_level 和 daily_itinerary 的舒适度判断。
- saving_tips 给出 2-4 条可执行的省钱建议。
- 不要返回 total / detail / daily_itinerary 字段。
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


def _travelers(state: TravelAgentState) -> int:
    try:
        return max(1, int(get_travelers(state) or 1))
    except (TypeError, ValueError):
        return 1


# 方法4：由 Σ(item.cost + item.leg_transport_cost) 翻转出预算明细。
# 住宿是行程级变量（整趟基本同一家酒店），按晚数 × 等级估算，不进入每日 item。
def _flip_budget_from_items(itinerary: Any, state: TravelAgentState) -> Dict[str, float]:
    food = transport = tickets = 0.0
    for day in ensure_list(itinerary, "daily_itinerary"):
        if not isinstance(day, dict):
            continue
        for item in ensure_list(day.get("items", []), "items"):
            if not isinstance(item, dict):
                continue
            category = item.get("cost_category")
            if category == "food":
                food += float(item.get("cost") or 0.0)
            elif category == "tickets":
                tickets += float(item.get("cost") or 0.0)
            transport += float(item.get("leg_transport_cost") or 0.0)

    level = get_budget_level(state)
    nights = max(1, (int(get_duration(state) or 1) - 1))
    travelers = _travelers(state)
    # 酒店：晚数 × 单晚单价（按等级），多人时按比例上浮（>2 人按人数/2 计房费）
    hotel_rate = {"economy": 200.0, "mid": 450.0, "luxury": 1000.0}.get(level, 450.0)
    room_factor = 1.0 if travelers <= 2 else travelers / 2.0
    hotel = round(hotel_rate * nights * room_factor, 2)

    return {
        "food": round(food, 2),
        "tickets": round(tickets, 2),
        "transport": round(transport, 2),
        "hotel": hotel,
    }


# 调用 LLM 生成预算等级与省钱建议，费用由后端从行程项汇总翻转得出。
@trace_span("agents.budget_agent.budget_agent_node")
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
    raw = ensure_dict(parsed.get("budget"), "budget")

    # 方法4：明细与总额均由行程项翻转，不再依赖 LLM 拍脑袋
    detail = _flip_budget_from_items(get_draft_daily_itinerary(state) or get_daily_itinerary(state), state)
    total = round(sum(detail.values()), 2)

    level = _as_text(raw.get("level"), get_budget_level(state))
    if level not in {"economy", "mid", "luxury"}:
        level = get_budget_level(state)

    tips = [_as_text(tip) for tip in ensure_list(raw.get("saving_tips", []), "saving_tips")]

    # 文本预算(supervisor 抽取)优先；仅在缺失时才用 budget_level 推导兜底，不覆盖已有上限
    existing_max = state.get("budget_max_allowed")
    if existing_max:
        max_allowed = float(existing_max)
    else:
        _LEVEL_DAILY_PER_PERSON = {"economy": 300.0, "mid": 600.0, "luxury": 1200.0}
        max_allowed = round(
            _LEVEL_DAILY_PER_PERSON.get(level, 600.0)
            * max(1, int(get_duration(state) or 1))
            * _travelers(state) * 1.15,
            2,
        )

    return {
        "draft_budget": {
            "level": level,
            "total": float(total),
            "detail": detail,
            "saving_tips": [tip for tip in tips if tip],
        },
        "budget_max_allowed": max_allowed,
        # 重翻 total 完成，清除脏标记，避免 validator 下一轮重复触发 budget_agent 死循环。
        "budget_dirty": False,
        # 预算自动微调闭环结束：削减后的行程已重算，清除标记，避免 validator 误判仍要削减。
        "auto_reduce_budget": False,
    }
