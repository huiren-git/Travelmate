import asyncio
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# 构造图工作流测试使用的初始 State。
def _initial_state(next_node="itinerary_agent", destination="北京"):
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content="帮我规划北京2日游，预算中等")],
        "user_id": "test-user",
        "thread_id": "test-thread",
        "destination": destination,
        "origin": "上海",
        "start_date": "2026-08-10",
        "duration": 2,
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
        "current_mode": "plan",
        "current_time": None,
        "validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
        "next_node": next_node,
    }


# 生成一个不依赖真实 LLM 的行程节点替身。
def _fake_itinerary_agent(calls):
    # 执行伪造行程节点并返回固定行程。
    async def node(state):
        calls.append("itinerary_agent")
        assert state["current_mode"] == "plan"
        return {
            "draft_daily_itinerary": [
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
            ],
            "validation_attempts": 0,
        }

    return node


# 生成一个不依赖真实 LLM 的预算节点替身。
def _fake_budget_agent(calls):
    # 执行伪造预算节点并返回固定预算。
    async def node(state):
        calls.append("budget_agent")
        return {
            "budget": {
                "level": "mid",
                "total": 1200.0,
                "detail": {"transport": 300.0, "hotel": 600.0, "food": 200.0, "tickets": 100.0},
                "saving_tips": ["错峰出行"],
            }
        }

    return node


# 生成一个跳过真实 API 的预取节点替身。
def _fake_pre_fetcher(calls):
    # 执行伪造预取节点并返回固定天气和景点数据。
    async def node(state):
        calls.append("pre_fetcher")
        assert state["destination"] == "北京"
        return {
            "weather_info": {"city": "北京", "temp": 28, "desc": "晴"},
            "fetched_attractions": [
                {"name": "故宫博物院", "rating": 4.8, "price": 60},
                {"name": "天坛公园", "rating": 4.6, "price": 34},
            ],
        }

    return node


# 生成一个可控路由结果的 Supervisor 节点替身。
def _fake_supervisor(calls, next_node):
    # 执行伪造 Supervisor 节点并返回指定路由。
    async def node(state):
        calls.append("supervisor")
        assert state["weather_info"] is None
        assert state["fetched_attractions"] is None
        return {
            "next_node": next_node,
            "current_mode": "plan",
            "destination": state.get("destination") or "北京",
        }

    return node


# 使用替身节点构建真实 graph 结构。
def _build_graph_with_fakes(monkeypatch, tmp_path, calls, next_node):
    pytest.importorskip("langgraph.graph", reason="Install project dependencies before running graph workflow tests")

    import src.graph.graph as graph_module

    monkeypatch.setattr(graph_module, "pre_fetcher_node", _fake_pre_fetcher(calls))
    monkeypatch.setattr(graph_module, "supervisor_node", _fake_supervisor(calls, next_node))
    monkeypatch.setattr(graph_module, "itinerary_agent_node", _fake_itinerary_agent(calls))
    monkeypatch.setattr(graph_module, "budget_agent_node", _fake_budget_agent(calls))
    async def fake_summary(*_args, **_kwargs):
        return "行程已生成"
    monkeypatch.setattr("src.graph.validator._generate_summary_text", fake_summary)
    return graph_module, graph_module.build_graph(str(tmp_path / "travelmate-test.db"))


# 验证 graph 在行程分支中能按顺序推进到 Validator。
def test_graph_workflow_generates_itinerary_then_budget_without_real_llm(monkeypatch, tmp_path):
    calls = []
    graph_module, graph = _build_graph_with_fakes(monkeypatch, tmp_path, calls, "itinerary_agent")

    final_state = asyncio.run(
        graph.ainvoke(
            _initial_state("itinerary_agent", destination=None),
            config={"configurable": {"thread_id": "test-itinerary-thread"}},
        )
    )

    assert calls == ["supervisor", "pre_fetcher", "itinerary_agent", "budget_agent"]
    assert final_state["is_finished"] is True
    assert final_state["validation_attempts"] == 2
    assert final_state["validation_report"]["passed"] is True
    assert final_state["next_node"] == "budget_agent"
    assert final_state["daily_itinerary"][0]["items"]
    assert final_state["budget"]["total"] == 1200.0
    assert graph_module.validator_router({"is_finished": True, "next_node": "budget_agent"}) == "__end__"


# 验证 graph 在预算分支中能按顺序推进到 Validator。
def test_graph_workflow_generates_budget_without_real_llm(monkeypatch, tmp_path):
    calls = []
    _, graph = _build_graph_with_fakes(monkeypatch, tmp_path, calls, "budget_agent")

    final_state = asyncio.run(
        graph.ainvoke(
            _initial_state("budget_agent"),
            config={"configurable": {"thread_id": "test-budget-thread"}},
        )
    )

    assert calls == ["supervisor", "pre_fetcher", "budget_agent"]
    assert final_state["is_finished"] is True
    assert final_state["validation_attempts"] == 1
    assert final_state["validation_report"]["passed"] is True
    assert final_state["next_node"] == "budget_agent"
    assert final_state["budget"]["total"] > 0
    assert final_state["daily_itinerary"] is None


# 验证 graph 的条件路由函数覆盖结束、预算和重试分支。
def test_graph_routers(monkeypatch, tmp_path):
    calls = []
    graph_module, _ = _build_graph_with_fakes(monkeypatch, tmp_path, calls, "itinerary_agent")

    assert graph_module.supervisor_router({"is_finished": True, "next_node": "itinerary_agent"}) == "__end__"
    assert graph_module.supervisor_router({"is_finished": False, "next_node": "budget_agent"}) == "pre_fetcher"
    assert graph_module.pre_fetcher_router({"is_finished": False, "next_node": "budget_agent"}) == "budget_agent"
    assert graph_module.validator_router({"is_finished": False, "next_node": "itinerary_agent", "validation_attempts": 0}) == "itinerary_agent"
    assert graph_module.validator_router({"is_finished": False, "next_node": "budget_agent", "validation_attempts": 0}) == "budget_agent"
    assert graph_module.validator_router({"is_finished": False, "next_node": "budget_agent", "validation_attempts": 3}) == "__end__"
    assert graph_module.validator_router({"is_finished": True, "next_node": "itinerary_agent", "validation_attempts": 1}) == "__end__"
