import json
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class FakeJsonLLM:
    # 初始化假 LLM，并记录每次收到的消息。
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    # 模拟 LangChain 异步调用并返回 JSON 文本。
    async def ainvoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=json.dumps(self.payload, ensure_ascii=False))


# 构造 Supervisor 链路测试使用的初始 State。
def _initial_state(message="帮我规划北京3日游，预算中等"):
    return {
        "messages": [HumanMessage(content=message)],
        "user_id": "test-user",
        "thread_id": "test-thread",
        "destination": None,
        "origin": "上海",
        "start_date": "2026-08-10",
        "duration": None,
        "structured_preferences": {
            "budget_level": "mid",
            "pace": "relaxed",
            "interests": ["history", "food"],
            "travelers": 2,
        },
        "weather_info": None,
        "fetched_attractions": None,
        "daily_itinerary": None,
        "budget": None,
        "draft_daily_itinerary": None,
        "draft_budget": None,
        "plan_mode": "plan",
        "current_mode": "plan",
        "current_time": None,
        "validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
        "next_node": None,
    }


# 构造一个能通过 Validator 的行程 LLM 响应。
def _itinerary_payload():
    return {
        "daily_itinerary": [
            {
                "day": 1,
                "date": "2026-08-10",
                "items": [
                    {
                        "time": "09:00",
                        "activity": "故宫博物院",
                        "duration": "2h",
                        "address": "北京市东城区景山前街4号",
                        "status": "upcoming",
                        "tips": "建议提前预约门票",
                    },
                    {
                        "time": "12:00",
                        "activity": "午餐",
                        "duration": "1h",
                        "address": "王府井",
                        "status": "upcoming",
                        "tips": "避开高峰排队",
                    },
                    {
                        "time": "18:00",
                        "activity": "晚餐",
                        "duration": "1h",
                        "address": "前门大街",
                        "status": "upcoming",
                        "tips": "选择评价较高的餐厅",
                    },
                ],
            }
        ]
    }


# 构造一个能通过 Validator 的预算 LLM 响应。
def _budget_payload():
    return {
        "budget": {
            "level": "mid",
            "total": 2800.0,
            "detail": {
                "transport": 600.0,
                "hotel": 1200.0,
                "food": 650.0,
                "tickets": 350.0,
            },
            "saving_tips": ["提前预订酒店", "景点门票使用官方渠道"],
        }
    }


# 验证 Supervisor 能路由到 itinerary_agent 并完整推进到 Validator。
@pytest.mark.asyncio
async def test_supervisor_routes_to_itinerary_and_workflow_reaches_validator(monkeypatch):
    from src.agents import itinerary_agent as itinerary_module
    from src.agents import supervisor as supervisor_module
    from src.graph.graph import build_graph

    routing_llm = FakeJsonLLM(
        {
            "next_node": "itinerary_agent",
            "plan_mode": "plan",
            "destination": "北京",
            "duration": 3,
            "reply": None,
            "reason": "用户要求规划北京3日游。",
        }
    )
    itinerary_llm = FakeJsonLLM(_itinerary_payload())
    monkeypatch.setattr(supervisor_module, "get_supervisor_llm", lambda: routing_llm)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: itinerary_llm)

    graph = build_graph(":memory:")
    final_state = await graph.ainvoke(
        _initial_state(),
        config={"configurable": {"thread_id": "supervisor-itinerary-test"}},
    )

    assert routing_llm.calls, "Supervisor should call the routing LLM"
    assert itinerary_llm.calls, "Itinerary agent should call its LLM"
    assert final_state["next_node"] == "itinerary_agent"
    assert final_state["plan_mode"] == "plan"
    assert final_state["destination"] == "北京"
    assert final_state["duration"] == 3
    assert final_state["daily_itinerary"]
    assert final_state["budget"] is None
    assert final_state["validation_report"]["passed"] is True
    assert final_state["is_finished"] is True


# 验证 Supervisor 能路由到 budget_agent 并完整推进到 Validator。
@pytest.mark.asyncio
async def test_supervisor_routes_to_budget_and_workflow_reaches_validator(monkeypatch):
    from src.agents import budget_agent as budget_module
    from src.agents import supervisor as supervisor_module
    from src.graph.graph import build_graph

    routing_llm = FakeJsonLLM(
        {
            "next_node": "budget_agent",
            "plan_mode": "plan",
            "destination": "北京",
            "duration": 2,
            "reply": None,
            "reason": "用户主要询问预算。",
        }
    )
    budget_llm = FakeJsonLLM(_budget_payload())
    monkeypatch.setattr(supervisor_module, "get_supervisor_llm", lambda: routing_llm)
    monkeypatch.setattr(budget_module, "get_budget_llm", lambda: budget_llm)

    graph = build_graph(":memory:")
    final_state = await graph.ainvoke(
        _initial_state("帮我估算北京2日游要花多少钱"),
        config={"configurable": {"thread_id": "supervisor-budget-test"}},
    )

    assert routing_llm.calls, "Supervisor should call the routing LLM"
    assert budget_llm.calls, "Budget agent should call its LLM"
    assert final_state["next_node"] == "budget_agent"
    assert final_state["plan_mode"] == "plan"
    assert final_state["destination"] == "北京"
    assert final_state["duration"] == 2
    assert final_state["budget"]["level"] == "mid"
    assert final_state["daily_itinerary"] is None
    assert final_state["validation_report"]["passed"] is True
    assert final_state["is_finished"] is True


# 验证信息不足时 Supervisor 会结束当前链路并追问用户。
@pytest.mark.asyncio
async def test_supervisor_asks_for_missing_fields_when_llm_ends(monkeypatch):
    from src.agents import supervisor as supervisor_module
    from src.agents.supervisor import supervisor_node

    routing_llm = FakeJsonLLM(
        {
            "next_node": "__end__",
            "plan_mode": "plan",
            "destination": None,
            "duration": None,
            "reply": "请告诉我目的地和旅行天数。",
            "reason": "缺少必要信息。",
        }
    )
    monkeypatch.setattr(supervisor_module, "get_supervisor_llm", lambda: routing_llm)

    result = await supervisor_node(_initial_state("帮我规划一次旅行"))

    assert routing_llm.calls, "Supervisor should call the routing LLM"
    assert result["next_node"] == "__end__"
    assert result["is_finished"] is True
    assert result["messages"][0].content == "请告诉我目的地和旅行天数。"


# 验证 Supervisor 会将明显的修改类请求识别为 REPLAN 模式。
@pytest.mark.asyncio
async def test_supervisor_detects_replan_from_existing_itinerary(monkeypatch):
    from src.agents import supervisor as supervisor_module
    from src.agents.supervisor import supervisor_node

    state = _initial_state("下午别去南锣鼓巷了，换一个轻松点的安排")
    state["destination"] = "北京"
    state["duration"] = 2
    state["daily_itinerary"] = _itinerary_payload()["daily_itinerary"]
    routing_llm = FakeJsonLLM(
        {
            "next_node": "itinerary_agent",
            "plan_mode": "plan",
            "destination": None,
            "duration": None,
            "reply": None,
            "reason": "用户要求调整已有行程。",
        }
    )
    monkeypatch.setattr(supervisor_module, "get_supervisor_llm", lambda: routing_llm)

    result = await supervisor_node(state)

    assert routing_llm.calls, "Supervisor should call the routing LLM"
    assert '"plan_mode": "plan | replan"' in routing_llm.calls[0][0].content
    assert "必须输出 plan_mode" in routing_llm.calls[0][0].content
    assert result["next_node"] == "itinerary_agent"
    assert result["plan_mode"] == "replan"
    assert result["current_mode"] == "replan"
