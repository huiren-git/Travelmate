import json
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents import itinerary_agent as itinerary_module
from src.agents.itinerary_agent import itinerary_agent_node
from src.graph import validator as validator_module
from src.graph.validator import validator_node


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
    assert itinerary[0]["items"][:3] == original_locked_items
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


# 验证 Validator 通过后才会将 REPLAN 草稿提升为正式行程。
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
    assert result["daily_itinerary"] == draft_itinerary
    assert result["daily_itinerary"] != original_itinerary
    assert result["draft_daily_itinerary"] is None


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
