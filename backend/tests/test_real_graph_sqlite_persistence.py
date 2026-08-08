import sqlite3
import sys
import uuid
from importlib.util import find_spec
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


PROMPT = "帮我设计一个北京3日游的旅行计划"
CITY = "北京"
START_DATE = "2026-08-10"


# 检查真实集成测试所需的配置值是否存在。
def _require_key(value: str, name: str) -> None:
    if not value:
        pytest.skip(f"{name} is required for real graph integration tests")


# 根据默认模型供应商检查对应的 LLM API Key 是否存在。
def _require_default_llm_key(settings) -> None:
    provider = settings.default_llm_model.split(":", 1)[0]
    key_by_provider = {
        "openai": (settings.openai_api_key, "OPENAI_API_KEY"),
        "qwen": (settings.qwen_api_key, "QWEN_API_KEY"),
        "deepseek": (settings.deepseek_api_key, "DEEPSEEK_API_KEY"),
        "moonshot": (settings.moonshot_api_key, "MOONSHOT_API_KEY"),
    }
    if provider not in key_by_provider:
        pytest.skip(f"Unsupported default LLM provider for integration test: {provider}")
    _require_key(*key_by_provider[provider])

    package_by_provider = {
        "openai": "langchain_openai",
        "qwen": "langchain_community",
        "deepseek": "langchain_deepseek",
        "moonshot": "langchain_community",
    }
    package_name = package_by_provider.get(provider)
    if package_name and find_spec(package_name) is None:
        pytest.skip(f"{package_name} is required for default LLM provider {provider}")


# 构造会触发真实天气和地图预取的初始 State。
def _initial_state(thread_id: str) -> dict:
    return {
        "messages": [HumanMessage(content=PROMPT)],
        "user_id": "integration-test-user",
        "thread_id": thread_id,
        "destination": CITY,
        "origin": "上海",
        "start_date": START_DATE,
        "duration": 3,
        "structured_preferences": {
            "budget_level": "mid",
            "pace": "relaxed",
            "interests": ["history", "food", "culture"],
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
        "next_node": None,
    }


# 校验真实链路返回的旅行计划 State 是否完整。
def _assert_trip_state(state: dict) -> None:
    assert state["destination"] == CITY
    assert state["duration"] == 3
    assert state["next_node"] == "itinerary_agent"
    assert state["is_finished"] is True
    assert state["validation_report"]["passed"] is True
    assert state["weather_info"]["city"] == CITY
    assert state["weather_info"]["date"] == START_DATE
    assert state["weather_info"]["desc"] != "未知（API调用失败）"
    assert isinstance(state["fetched_attractions"], list)
    assert state["fetched_attractions"], "真实地图 API 没有返回北京景点数据"
    assert isinstance(state["daily_itinerary"], list)
    assert len(state["daily_itinerary"]) == 3
    assert all(day.get("items") for day in state["daily_itinerary"])
    assert state["budget"] is None


# 查询 SQLite checkpoint 表中指定 thread_id 的记录数。
def _count_sqlite_checkpoints(db_path: Path, thread_id: str) -> int:
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "checkpoints" in tables
        row = conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    return int(row[0])


# 验证真实 LLM、天气、地图 API 生成的北京三日游结果能够持久化到 SQLite。
@pytest.mark.asyncio
async def test_beijing_three_day_trip_plan_real_llm_api_and_sqlite_persistence(monkeypatch, tmp_path):
    checkpoint_module = pytest.importorskip(
        "langgraph.checkpoint.sqlite.aio",
        reason="Install langgraph-checkpoint-sqlite before running SQLite persistence tests",
    )
    AsyncSqliteSaver = checkpoint_module.AsyncSqliteSaver

    from src.config.settings import settings
    from src.graph.graph import build_graph
    import src.services.redis_client as redis_service

    _require_default_llm_key(settings)
    _require_key(settings.qweather_api_key, "QWEATHER_API_KEY")
    _require_key(settings.amap_api_key, "AMAP_API_KEY")
    monkeypatch.setattr(redis_service, "redis_client", None)

    db_path = tmp_path / "beijing-three-day-checkpoints.sqlite"
    thread_id = f"real-beijing-trip-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncSqliteSaver.from_conn_string(str(db_path)) as checkpointer:
        if hasattr(checkpointer, "setup"):
            await checkpointer.setup()
        graph = build_graph(checkpointer=checkpointer)
        final_state = await graph.ainvoke(_initial_state(thread_id), config=config)
        persisted_snapshot = await graph.aget_state(config)

    _assert_trip_state(final_state)
    _assert_trip_state(persisted_snapshot.values)
    assert db_path.exists()
    assert db_path.stat().st_size > 0
    assert _count_sqlite_checkpoints(db_path, thread_id) > 0
