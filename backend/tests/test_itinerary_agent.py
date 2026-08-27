import json
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents import itinerary_agent as itinerary_module
from src.agents.itinerary_agent import itinerary_agent_node
from src.core.exceptions import AppException
from src.graph import validator as validator_module
from src.graph.validator import validator_node
from src.utils.state_utils import get_start_date


class FakeJsonLLM:
    """模拟返回 JSON 行程的异步 LLM。"""

    # 初始化假 LLM，并记录收到的消息。
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    # 模拟 LangChain 异步调用。
    async def ainvoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=json.dumps(self.payload, ensure_ascii=False))


@pytest.mark.parametrize(
    ("current_time", "expected_date", "expected_hint"),
    [
        ("2026-08-24T03:00:00Z", "2026-08-24", "11:00"),
        ("2026-08-24T04:00:00Z", "2026-08-25", "09:00"),
        ("2026-08-24T08:11:38.828Z", "2026-08-25", "09:00"),
    ],
)
def test_missing_start_date_uses_local_remaining_time_threshold(
    current_time,
    expected_date,
    expected_hint,
):
    state = {"start_date": None, "current_time": current_time}

    assert get_start_date(state).isoformat() == expected_date
    assert itinerary_module._first_day_start_hint(state) == expected_hint


def test_initial_plan_removes_expired_items_and_forces_upcoming_status():
    state = {
        "start_date": None,
        "current_time": "2026-08-24T03:00:00Z",
    }
    itinerary = [
        {
            "day": 1,
            "date": "2026-08-24",
            "items": [
                {"time": "09:00", "activity": "过期项目", "status": "completed"},
                {"time": "12:00", "activity": "午餐", "status": "completed"},
                {"time": "18:00", "activity": "晚餐", "status": "ongoing"},
            ],
        }
    ]

    result = itinerary_module._enforce_initial_plan_constraints(itinerary, state)

    assert [item["activity"] for item in result[0]["items"]] == ["午餐", "晚餐"]
    assert {item["status"] for item in result[0]["items"]} == {"upcoming"}


def test_initial_plan_uses_tomorrow_at_nine_when_twelve_hours_remain():
    state = {
        "start_date": None,
        "current_time": "2026-08-24T04:00:00Z",
    }
    itinerary = [
        {
            "day": 1,
            "date": "2026-08-24",
            "items": [
                {"time": "09:00", "activity": "首个项目", "status": "completed"},
            ],
        }
    ]

    result = itinerary_module._enforce_initial_plan_constraints(itinerary, state)

    assert result[0]["date"] == "2026-08-25"
    assert result[0]["items"][0]["time"] == "09:00"
    assert result[0]["items"][0]["status"] == "upcoming"


@pytest.fixture(autouse=True)
def fake_activity_image_lookup(monkeypatch):
    async def fake_fetch_activity_image_url(destination, activity):
        return "https://amap.example.com/default.jpg"

    monkeypatch.setattr(
        itinerary_module,
        "_fetch_activity_image_url",
        fake_fetch_activity_image_url,
    )


# 构造 REPLAN 测试使用的 State。
def _replan_state():
    return {
        "messages": [HumanMessage(content="下午别去南锣鼓巷了，换一个轻松点的安排")],
        "user_id": "test-user",
        "thread_id": "test-thread",
        "destination": "北京",
        "origin": "上海",
        "start_date": "2026-08-10",
        "duration": 2,
        "structured_preferences": {
            "budget_level": "mid",
            "pace": "relaxed",
            "interests": ["history", "food"],
            "travelers": 2,
        },
        "weather_info": {"city": "北京", "desc": "晴"},
        "fetched_attractions": [{"name": "北海公园", "rating": 4.7}],
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
                        "status": "completed",
                        "tips": "已完成，不要改动",
                    },
                    {
                        "time": "12:00",
                        "activity": "午餐",
                        "duration": "1h",
                        "address": "王府井",
                        "status": "ongoing",
                        "tips": "正在进行，不要改动",
                    },
                    {
                        "time": "14:00",
                        "activity": "景山公园",
                        "duration": "1h",
                        "address": "北京市西城区景山西街44号",
                        "status": "upcoming",
                        "tips": "早于 current_time，也要锁定",
                    },
                    {
                        "time": "16:00",
                        "activity": "南锣鼓巷",
                        "duration": "2h",
                        "address": "北京市东城区南锣鼓巷",
                        "status": "upcoming",
                        "tips": "可以修改",
                    },
                ],
            },
            {
                "day": 2,
                "date": "2026-08-11",
                "items": [
                    {
                        "time": "09:00",
                        "activity": "天坛公园",
                        "duration": "2h",
                        "address": "北京市东城区天坛东路甲1号",
                        "status": "upcoming",
                        "tips": "可以修改",
                    }
                ],
            },
        ],
        "budget": None,
        "draft_daily_itinerary": None,
        "draft_budget": None,
        "plan_mode": "replan",
        "current_mode": "replan",
        "current_time": "2026-08-10T15:00:00",
        "validation_attempts": 0,
        "hard_validation_attempts": 0,
        "soft_validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
        "next_node": "itinerary_agent",
    }


def test_itinerary_prompt_requires_lunch_and_dinner_items():
    system_prompt = itinerary_module._build_itinerary_messages(_replan_state())[0].content

    assert "每天必须有 1 个午餐 item" in system_prompt
    assert "每天必须有 1 个晚餐 item" in system_prompt
    assert "午餐/晚餐必须作为独立 itinerary item 输出" in system_prompt


# 将 Validator 的软评估 LLM 替换为可控 fake。
def _patch_validator_llm(monkeypatch, payload):
    fake_llm = FakeJsonLLM(payload)
    monkeypatch.setattr(validator_module, "get_validator_llm", lambda: fake_llm)
    return fake_llm


# 验证 REPLAN 模式会硬锁 completed、ongoing 和 current_time 之前的行程项。
@pytest.mark.asyncio
async def test_replan_keeps_locked_items_and_only_rewrites_editable_scope(monkeypatch):
    state = _replan_state()
    original_locked_items = deepcopy(state["daily_itinerary"][0]["items"][:3])
    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "09:00",
                            "activity": "把故宫改掉",
                            "duration": "3h",
                            "address": "错误地址",
                            "status": "upcoming",
                            "tips": "LLM 不应触碰",
                        },
                        {
                            "time": "14:00",
                            "activity": "把景山也改掉",
                            "duration": "2h",
                            "address": "错误地址",
                            "status": "upcoming",
                            "tips": "早于 current_time，不应触碰",
                        },
                        {
                            "time": "17:00",
                            "activity": "故宫博物院",
                            "duration": "1h",
                            "address": "重复已完成行程",
                            "status": "upcoming",
                            "tips": "不应重复输出已完成行程",
                        },
                        {
                            "time": "16:00",
                            "activity": "北海公园散步",
                            "duration": "2h",
                            "address": "北京市西城区文津街1号",
                            "status": "upcoming",
                            "tips": "替换开放区项目",
                        },
                    ],
                },
                {
                    "day": 2,
                    "date": "2026-08-11",
                    "items": [
                        {
                            "time": "10:00",
                            "activity": "颐和园",
                            "duration": "3h",
                            "address": "北京市海淀区新建宫门路19号",
                            "status": "ongoing",
                            "tips": "LLM 给错状态也要改回 upcoming",
                        }
                    ],
                },
            ]
        }
    )
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)
    itinerary = result["draft_daily_itinerary"]

    assert fake_llm.calls, "REPLAN 存在开放区时应该调用 LLM"
    assert "daily_itinerary" not in result
    for actual, expected in zip(itinerary[0]["items"][:3], original_locked_items):
        assert {key: value for key, value in actual.items() if key != "image_url"} == expected
        if "午餐" in expected["activity"]:
            assert actual["image_url"] == ""
        else:
            assert actual["image_url"] == "https://amap.example.com/default.jpg"
    assert [item["activity"] for item in itinerary[0]["items"]] == [
        "故宫博物院",
        "午餐",
        "景山公园",
        "北海公园散步",
    ]
    assert itinerary[1]["items"][0]["activity"] == "颐和园"
    assert itinerary[1]["items"][0]["status"] == "upcoming"

    system_prompt = fake_llm.calls[0][0].content
    payload = json.loads(fake_llm.calls[0][1].content)
    assert "不要重复输出已完成的行程" in system_prompt
    assert payload["editable_itinerary"][0]["items"][0]["activity"] == "南锣鼓巷"
    assert all(item["activity"] != "故宫博物院" for day in payload["editable_itinerary"] for item in day["items"])


# 验证 Itinerary Agent 在构建 Prompt 前用最新用户需求检索长期偏好，并注入给 LLM。
@pytest.mark.asyncio
async def test_itinerary_agent_retrieves_relevant_preferences_before_prompt(monkeypatch):
    state = _replan_state()
    calls = []

    async def fake_retrieve(user_id, query, memory_type="preference", top_k=5):
        calls.append(
            {
                "user_id": user_id,
                "query": query,
                "memory_type": memory_type,
                "top_k": top_k,
            }
        )
        return [
            {
                "text": "用户偏好：喜欢轻松散步和历史文化景点",
                "metadata": {"source": "itinerary_agent", "memory_type": "preference"},
                "score": 0.12,
            }
        ]

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "16:00",
                            "activity": "北海公园散步",
                            "duration": "2h",
                            "address": "北京市西城区文津街1号",
                            "status": "upcoming",
                            "tips": "符合轻松散步偏好",
                        }
                    ],
                }
            ]
        }
    )
    async def fake_store(state, user_message):
        return None

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    await itinerary_agent_node(state)

    assert calls == [
        {
            "user_id": "test-user",
            "query": "下午别去南锣鼓巷了，换一个轻松点的安排",
            "memory_type": "preference",
            "top_k": 5,
        }
    ]
    payload = json.loads(fake_llm.calls[0][1].content)
    assert payload["relevant_preferences"][0]["text"] == "用户偏好：喜欢轻松散步和历史文化景点"


# 验证 Itinerary Agent 会从用户偏好和修改决策中写入长期记忆。
@pytest.mark.asyncio
async def test_itinerary_agent_stores_preference_and_action_memories(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="我喜欢轻松一点，下午别去南锣鼓巷了，换成公园散步")]
    stored = []

    async def fake_add(user_id, text, memory_type="preference", metadata=None):
        stored.append(
            {
                "user_id": user_id,
                "text": text,
                "memory_type": memory_type,
                "metadata": metadata,
            }
        )
        return f"mem-{len(stored)}"

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "16:00",
                            "activity": "北海公园散步",
                            "duration": "2h",
                            "address": "北京市西城区文津街1号",
                            "status": "upcoming",
                            "tips": "轻松安排",
                        }
                    ],
                }
            ]
        }
    )
    async def fake_retrieve(*args, **kwargs):
        return []

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_add_memory", fake_add)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    await itinerary_agent_node(state)

    memory_types = {item["memory_type"] for item in stored}
    assert memory_types == {"preference", "action"}
    assert any("轻松" in item["text"] for item in stored if item["memory_type"] == "preference")
    assert any("换成公园散步" in item["text"] for item in stored if item["memory_type"] == "action")
    assert all(item["metadata"]["thread_id"] == "test-thread" for item in stored)


# 验证 PLAN 模式会同时检索偏好记忆和历史操作日志，并传给行程 LLM。
@pytest.mark.asyncio
async def test_plan_retrieves_preferences_and_action_logs_before_prompt(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="帮我规划北京两日游，尽量安排轻松一些")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    calls = []

    async def fake_retrieve_preferences(user_id, query):
        calls.append(("preference", user_id, query))
        return [{"text": "用户喜欢历史文化景点", "metadata": {}, "score": 0.1}]

    async def fake_retrieve_action_logs(user_id, query):
        calls.append(("action", user_id, query))
        return [{"text": "用户曾把步行线路改成公园散步", "metadata": {}, "score": 0.2}]

    async def fake_store(*_):
        return None

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "09:00",
                            "activity": "故宫博物院",
                            "duration": "3h",
                            "address": "北京市东城区景山前街4号",
                            "status": "upcoming",
                            "tips": "提前预约",
                        }
                    ],
                }
            ]
        }
    )
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve_preferences)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve_action_logs)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    await itinerary_agent_node(state)

    assert calls == [
        ("preference", "test-user", "帮我规划北京两日游，尽量安排轻松一些"),
        ("action", "test-user", "帮我规划北京两日游，尽量安排轻松一些"),
    ]
    payload = json.loads(fake_llm.calls[0][1].content)
    assert payload["relevant_preferences"][0]["text"] == "用户喜欢历史文化景点"
    assert payload["relevant_action_logs"][0]["text"] == "用户曾把步行线路改成公园散步"


@pytest.mark.asyncio
async def test_plan_adds_image_url_from_fetched_attractions(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing history trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = [
        {
            "name": "Forbidden City",
            "image_url": "https://example.com/forbidden-city.jpg",
        }
    ]

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "09:00",
                            "activity": "Forbidden City",
                            "duration": "2h",
                            "address": "Beijing",
                            "status": "upcoming",
                            "tips": "Book tickets early",
                        }
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert result["daily_itinerary"][0]["items"][0]["image_url"] == "https://example.com/forbidden-city.jpg"


@pytest.mark.asyncio
async def test_plan_backfills_missing_image_url_from_amap(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing nature trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []
    lookup_calls = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        lookup_calls.append((destination, activity))
        return "https://amap.example.com/beihai.jpg"

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "09:00",
                            "activity": "北海公园",
                            "duration": "2h",
                            "address": "北京市西城区文津街1号",
                            "status": "upcoming",
                            "tips": "上午游览",
                        }
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(
        itinerary_module,
        "_fetch_activity_image_url",
        fake_fetch_activity_image_url,
        raising=False,
    )
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert lookup_calls == [("北京", "北海公园")]
    assert result["daily_itinerary"][0]["items"][0]["image_url"] == "https://amap.example.com/beihai.jpg"


@pytest.mark.asyncio
async def test_plan_raises_when_missing_image_url_cannot_be_backfilled(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing mystery trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        return ""

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "09:00",
                            "activity": "不存在的幻想景点",
                            "duration": "2h",
                            "address": "北京",
                            "status": "upcoming",
                            "tips": "应被拦截",
                        }
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(
        itinerary_module,
        "_fetch_activity_image_url",
        fake_fetch_activity_image_url,
        raising=False,
    )
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    with pytest.raises(AppException) as exc_info:
        await itinerary_agent_node(state)

    assert exc_info.value.status_code == 422
    assert exc_info.value.details["activity"] == "不存在的幻想景点"


@pytest.mark.asyncio
async def test_plan_allows_meal_items_without_image_url(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing food and history trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []
    lookup_calls = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        lookup_calls.append((destination, activity))
        return ""

    fake_llm = FakeJsonLLM(
        {
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
                            "image_url": "https://example.com/forbidden-city.jpg",
                            "status": "upcoming",
                            "tips": "提前预约",
                        },
                        {
                            "time": "12:00",
                            "activity": "午餐：北京烤鸭",
                            "duration": "1h",
                            "address": "王府井",
                            "status": "upcoming",
                            "tips": "避开高峰",
                        },
                        {
                            "time": "18:00",
                            "activity": "晚餐：簋街小吃",
                            "duration": "1h",
                            "address": "簋街",
                            "status": "upcoming",
                            "tips": "选择评价较高的店",
                        },
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(
        itinerary_module,
        "_fetch_activity_image_url",
        fake_fetch_activity_image_url,
    )
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)
    items = result["daily_itinerary"][0]["items"]

    assert lookup_calls == []
    assert items[1]["activity"] == "午餐：北京烤鸭"
    assert items[1]["image_url"] == ""
    assert items[2]["activity"] == "晚餐：簋街小吃"
    assert items[2]["image_url"] == ""


@pytest.mark.asyncio
async def test_plan_allows_meal_time_restaurant_without_food_keyword(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing food and history trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []
    lookup_calls = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        lookup_calls.append((destination, activity))
        return ""

    fake_llm = FakeJsonLLM(
        {
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
                            "image_url": "https://example.com/forbidden-city.jpg",
                            "status": "upcoming",
                            "tips": "提前预约",
                        },
                        {
                            "time": "12:00",
                            "activity": "全聚德王府井店",
                            "duration": "1h",
                            "address": "王府井",
                            "status": "upcoming",
                            "tips": "避开高峰",
                        },
                        {
                            "time": "18:00",
                            "activity": "四季民福前门店",
                            "duration": "1h",
                            "address": "前门",
                            "status": "upcoming",
                            "tips": "提前取号",
                        },
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "_fetch_activity_image_url", fake_fetch_activity_image_url)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)
    items = result["daily_itinerary"][0]["items"]

    assert lookup_calls == []
    assert items[1]["activity"] == "全聚德王府井店"
    assert items[1]["image_url"] == ""
    assert items[2]["activity"] == "四季民福前门店"
    assert items[2]["image_url"] == ""


@pytest.mark.asyncio
async def test_plan_degrades_transport_item_without_image_url(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing transfer and history trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []
    lookup_calls = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        lookup_calls.append((destination, activity))
        return ""

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "08:00",
                            "activity": "乘地铁前往天安门",
                            "duration": "30min",
                            "address": "地铁站",
                            "status": "upcoming",
                            "tips": "避开早高峰",
                        },
                        {
                            "time": "09:00",
                            "activity": "故宫博物院",
                            "duration": "2h",
                            "address": "北京市东城区景山前街4号",
                            "image_url": "https://example.com/forbidden-city.jpg",
                            "status": "upcoming",
                            "tips": "提前预约",
                        },
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "_fetch_activity_image_url", fake_fetch_activity_image_url)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert lookup_calls == []
    assert result["daily_itinerary"][0]["items"][0]["image_url"] == ""


@pytest.mark.asyncio
async def test_plan_degrades_dining_item_without_image_url(monkeypatch):
    state = _replan_state()
    state["messages"] = [HumanMessage(content="Plan a Beijing leisure trip")]
    state["daily_itinerary"] = None
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["fetched_attractions"] = []
    lookup_calls = []

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    async def fake_fetch_activity_image_url(destination, activity):
        lookup_calls.append((destination, activity))
        return ""

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "15:00",
                            "activity": "咖啡休息",
                            "duration": "1h",
                            "address": "王府井",
                            "status": "upcoming",
                            "tips": "稍作休息",
                        },
                        {
                            "time": "16:00",
                            "activity": "故宫博物院",
                            "duration": "2h",
                            "address": "北京市东城区景山前街4号",
                            "image_url": "https://example.com/forbidden-city.jpg",
                            "status": "upcoming",
                            "tips": "提前预约",
                        },
                    ],
                }
            ]
        }
    )

    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_action_logs", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "_fetch_activity_image_url", fake_fetch_activity_image_url)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert lookup_calls == []
    assert result["daily_itinerary"][0]["items"][0]["image_url"] == ""


# 验证 REPLAN 成功合并行程后会调度操作日志，且不会阻塞返回结果。
@pytest.mark.asyncio
async def test_replan_schedules_action_log_after_generating_itinerary(monkeypatch):
    state = _replan_state()
    scheduled = []

    def fake_schedule(state, original_itinerary, updated_itinerary, user_message):
        scheduled.append(
            {
                "state": state,
                "original_itinerary": original_itinerary,
                "updated_itinerary": updated_itinerary,
                "user_message": user_message,
            }
        )

    async def fake_retrieve(*_):
        return []

    async def fake_store(*_):
        return None

    fake_llm = FakeJsonLLM(
        {
            "daily_itinerary": [
                {
                    "day": 1,
                    "date": "2026-08-10",
                    "items": [
                        {
                            "time": "16:00",
                            "activity": "北海公园散步",
                            "duration": "2h",
                            "address": "北京市西城区文津街1号",
                            "status": "upcoming",
                            "tips": "替换开放区项目",
                        }
                    ],
                },
                {
                    "day": 2,
                    "date": "2026-08-11",
                    "items": [
                        {
                            "time": "10:00",
                            "activity": "颐和园",
                            "duration": "3h",
                            "address": "北京市海淀区新建宫门路19号",
                            "status": "upcoming",
                            "tips": "安排在上午",
                        }
                    ],
                },
            ]
        }
    )
    monkeypatch.setattr(itinerary_module, "_retrieve_relevant_preferences", fake_retrieve)
    monkeypatch.setattr(itinerary_module, "_store_user_memory_candidates", fake_store)
    monkeypatch.setattr(itinerary_module, "_schedule_replan_action_log", fake_schedule)
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert result["draft_daily_itinerary"][0]["items"][-1]["activity"] == "北海公园散步"
    assert len(scheduled) == 1
    assert scheduled[0]["user_message"] == "下午别去南锣鼓巷了，换一个轻松点的安排"
    assert scheduled[0]["original_itinerary"] == state["daily_itinerary"]
    assert scheduled[0]["updated_itinerary"] == result["draft_daily_itinerary"]


# 验证 REPLAN 没有开放区时不会调用 LLM，并直接返回原行程。
@pytest.mark.asyncio
async def test_replan_returns_original_itinerary_when_everything_is_locked(monkeypatch):
    state = _replan_state()
    state["current_time"] = "2026-08-12T00:00:00"
    original_itinerary = deepcopy(state["daily_itinerary"])
    fake_llm = FakeJsonLLM({"daily_itinerary": []})
    monkeypatch.setattr(itinerary_module, "get_itinerary_llm", lambda: fake_llm)

    result = await itinerary_agent_node(state)

    assert fake_llm.calls == []
    assert "daily_itinerary" not in result
    assert result["draft_daily_itinerary"] == original_itinerary


# 行程质量通过后仍是草稿，必须继续通过预算校验才会提升为正式行程。
@pytest.mark.asyncio
async def test_validator_promotes_replan_draft_only_after_passed(monkeypatch):
    state = _replan_state()
    original_itinerary = deepcopy(state["daily_itinerary"])
    draft_itinerary = deepcopy(original_itinerary)
    draft_itinerary[0]["items"][-1] = {
        "time": "16:00",
        "activity": "北海公园散步",
        "duration": "2h",
        "address": "北京市西城区文津街1号",
        "status": "upcoming",
        "tips": "替换开放区项目",
    }
    state["draft_daily_itinerary"] = draft_itinerary
    fake_llm = _patch_validator_llm(
        monkeypatch,
        {
            "score": 92,
            "passed": True,
            "reason": "行程自然顺路，符合用户偏好",
            "issues": [],
            "suggestions": [],
        },
    )

    result = await validator_node(state)

    assert fake_llm.calls, "硬校验通过后应调用软评估 LLM"
    assert result["validation_report"]["passed"] is True
    assert result["validation_report"]["soft_evaluation"]["score"] == 92
    assert result["is_finished"] is False
    assert result["next_node"] == "budget_agent"
    assert "daily_itinerary" not in result
    assert result.get("draft_daily_itinerary") is None


# 验证 Validator 校验失败时不会覆写正式行程。
@pytest.mark.asyncio
async def test_validator_keeps_committed_itinerary_when_replan_draft_fails():
    state = _replan_state()
    state["draft_daily_itinerary"] = []

    result = await validator_node(state)

    assert result["validation_report"]["passed"] is False
    assert "draft_daily_itinerary is empty" in result["validation_report"]["errors"]
    assert result["soft_validation_attempts"] == 0
    assert result["validation_report"]["soft_evaluation"] is None
    assert "daily_itinerary" not in result


# 验证软评估低于阈值时不会放行。
@pytest.mark.asyncio
async def test_validator_rejects_itinerary_when_soft_score_below_threshold(monkeypatch):
    state = _replan_state()
    state["draft_daily_itinerary"] = deepcopy(state["daily_itinerary"])
    fake_llm = _patch_validator_llm(
        monkeypatch,
        {
            "score": 62,
            "passed": True,
            "reason": "行程强度过高且体验一般",
            "issues": ["景点串联不够顺路"],
            "suggestions": ["减少跨城区移动"],
        },
    )

    result = await validator_node(state)

    assert fake_llm.calls, "硬校验通过后应调用软评估 LLM"
    assert result["validation_report"]["passed"] is False
    assert "soft_score_below_threshold: 62 < 80" in result["validation_report"]["errors"]
    assert result["soft_validation_attempts"] == 1
    assert result["is_finished"] is False
    assert "daily_itinerary" not in result


# 验证软评估达到次数上限后不会继续调用 LLM，并停止自动重试。
@pytest.mark.asyncio
async def test_validator_stops_without_llm_when_soft_retry_limit_reached(monkeypatch):
    state = _replan_state()
    state["draft_daily_itinerary"] = deepcopy(state["daily_itinerary"])
    state["soft_validation_attempts"] = validator_module.MAX_SOFT_VALIDATION_ATTEMPTS
    fake_llm = _patch_validator_llm(
        monkeypatch,
        {
            "score": 100,
            "passed": True,
            "reason": "不应被调用",
            "issues": [],
            "suggestions": [],
        },
    )

    result = await validator_node(state)

    assert fake_llm.calls == []
    assert result["validation_report"]["passed"] is False
    assert result["validation_report"]["soft_evaluation"]["skipped"] is True
    assert result["is_finished"] is True
    assert "daily_itinerary" not in result


# 首次规划也必须经过草稿链路：质量重试耗尽时，不能把未通过的内容写入正式行程。
@pytest.mark.asyncio
async def test_validator_marks_initial_plan_failed_without_promoting_draft(monkeypatch):
    state = _replan_state()
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["daily_itinerary"] = None
    state["draft_daily_itinerary"] = [
        {
            "day": 1,
            "date": "2026-08-11",
            "items": [
                {"time": "12:00", "activity": "午餐", "duration": "1h", "status": "upcoming"},
                {"time": "18:00", "activity": "晚餐", "duration": "1h", "status": "upcoming"},
            ],
        }
    ]
    state["soft_validation_attempts"] = validator_module.MAX_SOFT_VALIDATION_ATTEMPTS
    fake_llm = _patch_validator_llm(monkeypatch, {"score": 100, "passed": True})

    result = await validator_node(state)

    assert fake_llm.calls == []
    assert result["is_finished"] is True
    assert result["terminal_status"] == "failed"
    assert "draft_daily_itinerary" not in result  # 未覆写，checkpoint 会保留原草稿供诊断
    assert "daily_itinerary" not in result
    assert "summary_text" not in result


# 预算校验通过才允许把首次规划的草稿行程和草稿预算一起晋升为正式数据。
@pytest.mark.asyncio
async def test_validator_promotes_initial_drafts_only_after_budget_passes(monkeypatch):
    state = _replan_state()
    state["plan_mode"] = "plan"
    state["current_mode"] = "plan"
    state["daily_itinerary"] = None
    state["budget"] = None
    state["draft_daily_itinerary"] = deepcopy(_replan_state()["daily_itinerary"])
    state["draft_budget"] = {
        "level": "mid",
        "total": 1000.0,
        "detail": {"transport": 100.0, "hotel": 600.0, "food": 200.0, "tickets": 100.0},
        "saving_tips": ["提前预订"],
    }
    state["next_node"] = "budget_agent"
    state["budget_max_allowed"] = 1500.0
    async def no_summary(*_args):
        return None
    monkeypatch.setattr(validator_module, "_generate_summary_text", no_summary)

    result = await validator_node(state)

    assert result["validation_report"]["passed"] is True
    assert result["is_finished"] is True
    assert result["terminal_status"] == "confirmed"
    assert result["daily_itinerary"] == state["draft_daily_itinerary"]
    assert result["budget"] == state["draft_budget"]
    assert result["draft_daily_itinerary"] is None
    assert result["draft_budget"] is None
