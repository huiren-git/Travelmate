import pytest

from src.graph import validator as validator_module
from src.graph.validator import validator_node


def _budget_state():
    return {
        "budget": {
            "level": "mid",
            "total": 1300.0,
            "detail": {
                "transport": 300.0,
                "hotel": 600.0,
                "food": 300.0,
                "tickets": 100.0,
            },
            "saving_tips": ["提前预订"],
        },
        "budget_max_allowed": 1000.0,
        "next_node": "budget_agent",
        "plan_mode": "plan",
        "current_mode": "plan",
        "validation_attempts": 0,
        "hard_validation_attempts": 0,
        "soft_validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
    }


class NoTriggerHandler:
    """模拟不需要用户决策的处理器。"""

    checked = 0

    # 记录检查次数并返回未命中。
    def should_trigger(self, state):
        type(self).checked += 1
        return False

    # 返回空 payload 以满足处理器接口。
    def build_payload(self, state):
        return {}


class BrokenHandler:
    """模拟执行时异常的处理器。"""

    checked = 0

    # 抛出异常以验证其他处理器仍会继续检查。
    def should_trigger(self, state):
        type(self).checked += 1
        raise RuntimeError("handler unavailable")

    # 返回空 payload 以满足处理器接口。
    def build_payload(self, state):
        return {}


class FirstDecisionHandler:
    """模拟第一个需要用户决策的处理器。"""

    checked = 0

    # 记录检查次数并返回命中。
    def should_trigger(self, state):
        type(self).checked += 1
        return True

    # 返回前端展示的第一个决策请求。
    def build_payload(self, state):
        return {"title": "确认预算方案"}


class SecondDecisionHandler:
    """模拟第二个需要用户决策的处理器。"""

    checked = 0

    # 记录检查次数并返回命中。
    def should_trigger(self, state):
        type(self).checked += 1
        return True

    # 返回前端展示的第二个决策请求。
    def build_payload(self, state):
        return {"title": "确认酒店方案"}


# 重置所有 fake handler 的调用计数。
def _reset_handler_counters():
    for handler_cls in (
        NoTriggerHandler,
        BrokenHandler,
        FirstDecisionHandler,
        SecondDecisionHandler,
    ):
        handler_cls.checked = 0


# 验证 Validator 会遍历所有注册处理器并打包多个用户决策请求。
@pytest.mark.asyncio
async def test_validator_collects_all_registered_user_decision_handlers(monkeypatch):
    _reset_handler_counters()
    captured_payloads = []
    monkeypatch.setattr(
        validator_module,
        "_handler_registry",
        {
            "no_trigger": NoTriggerHandler,
            "broken": BrokenHandler,
            "budget_confirmation": FirstDecisionHandler,
            "hotel_confirmation": SecondDecisionHandler,
        },
    )
    monkeypatch.setattr(
        validator_module,
        "interrupt",
        lambda payload: captured_payloads.append(payload),
    )

    result = await validator_node(_budget_state())

    assert NoTriggerHandler.checked == 1
    assert BrokenHandler.checked == 1
    assert FirstDecisionHandler.checked == 1
    assert SecondDecisionHandler.checked == 1
    assert len(captured_payloads) == 1
    assert captured_payloads[0]["type"] == "multiple_user_decisions"
    assert [item["interrupt_type"] for item in captured_payloads[0]["interrupts"]] == [
        "budget_confirmation",
        "hotel_confirmation",
    ]
    assert result["validation_report"]["user_decision_requests"] == captured_payloads[0]["interrupts"]


# 验证硬校验失败时不会触发任何用户决策处理器。
@pytest.mark.asyncio
async def test_validator_skips_user_decision_handlers_when_hard_validation_fails(monkeypatch):
    _reset_handler_counters()
    captured_payloads = []
    state = _budget_state()
    state["budget"]["detail"]["hotel"] = 100.0
    monkeypatch.setattr(
        validator_module,
        "_handler_registry",
        {"budget_confirmation": FirstDecisionHandler},
    )
    monkeypatch.setattr(
        validator_module,
        "interrupt",
        lambda payload: captured_payloads.append(payload),
    )

    result = await validator_node(state)

    assert result["validation_report"]["passed"] is False
    assert FirstDecisionHandler.checked == 0
    assert captured_payloads == []
