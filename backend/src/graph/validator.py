"""Validator node for workflow output verification."""

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from src.handlers.registry import _handler_registry
from src.graph.state import TravelAgentState
from src.utils.llm_utils import call_llm, ensure_dict, extract_json, message_content
from src.utils.state_utils import (
    get_budget_level,
    get_budget,
    get_daily_itinerary,
    get_draft_daily_itinerary,
    get_duration,
    get_hard_validation_attempts,
    get_plan_mode,
    get_pace,
    get_soft_validation_attempts,
    get_structured_preferences,
    get_validation_attempts,
    get_destination,
    parse_duration_to_minutes,
    parse_time_to_minutes,
)

logger = logging.getLogger("travelmate.agents.validator")

MAX_VALIDATION_ATTEMPTS = 3
MAX_HARD_VALIDATION_ATTEMPTS = 3
MAX_SOFT_VALIDATION_ATTEMPTS = 2
SOFT_SCORE_THRESHOLD = 80


def get_validator_llm():
    """
    获取用于 Validator 的 LLM 实例，温度固定为 0.0
    """
    from src.agents.base import get_llm

    return get_llm(temperature=0.0)


def _check_time_overlaps(itinerary: list) -> list:
    """
    检查每天的行程是否存在时间重叠，返回警告列表
    """
    warnings = []
    for day in itinerary:
        items = day.get("items", [])
        sorted_items = sorted(
            [(idx, item) for idx, item in enumerate(items)],
            key=lambda x: parse_time_to_minutes(x[1].get("time", "00:00")),
        )
        for i in range(len(sorted_items) - 1):
            _, current = sorted_items[i]
            _, next_item = sorted_items[i + 1]
            start1 = parse_time_to_minutes(current.get("time", ""))
            dur_minutes = parse_duration_to_minutes(current.get("duration", "0h"))
            start2 = parse_time_to_minutes(next_item.get("time", ""))
            if start1 != -1 and start2 != -1 and start1 + dur_minutes > start2:
                warnings.append(
                    f"Day {day.get('day')}: '{current.get('activity')}' 和 '{next_item.get('activity')}' 时间重叠"
                )
                break
    return warnings


def _check_budget_consistency(budget: dict) -> list:
    errors = []
    if not budget:
        return errors
    total = budget.get("total", 0)
    detail = budget.get("detail", {})
    if not detail:
        return errors
    sum_detail = sum(float(value or 0) for value in detail.values())
    if abs(float(total or 0) - sum_detail) > 0.01:
        errors.append(f"预算总额({total})与明细合计({sum_detail})不一致")
    return errors


# 检查每天是否覆盖午餐和晚餐时段。
def _check_meal_time_coverage(itinerary: list) -> list:
    warnings = []
    for day in itinerary:
        items = day.get("items", [])
        times = [parse_time_to_minutes(item.get("time", "")) for item in items]
        lunch_zone = (11 * 60 + 30, 13 * 60 + 30)
        dinner_zone = (17 * 60 + 30, 19 * 60 + 30)
        has_lunch = any(lunch_zone[0] <= t <= lunch_zone[1] for t in times)
        has_dinner = any(dinner_zone[0] <= t <= dinner_zone[1] for t in times)
        if not has_lunch:
            warnings.append(f"Day {day.get('day')} 没有覆盖午餐时段(11:30-13:30)")
        if not has_dinner:
            warnings.append(f"Day {day.get('day')} 没有覆盖晚餐时段(17:30-19:30)")
    return warnings


# 检查行程结构是否完整。
def _validate_itinerary(
    itinerary: list,
    state: TravelAgentState,
    field_name: str = "daily_itinerary",
) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    if not itinerary:
        errors.append(f"{field_name} is empty")
        return errors, warnings

    activities = []
    for day in itinerary:
        items = day.get("items", [])
        if not items:
            warnings.append(f"day {day.get('day')} has no itinerary items")
        for item in items:
            activities.append(item.get("activity", ""))
    if len(set(activities)) < len(activities):
        warnings.append("duplicate activities found")

    warnings.extend(_check_time_overlaps(itinerary))
    warnings.extend(_check_meal_time_coverage(itinerary))

    pace = get_pace(state)
    avg_items = sum(len(day.get("items", [])) for day in itinerary) / len(itinerary)
    if pace == "relaxed" and avg_items > 4:
        warnings.append(f"当前偏休闲但每天平均{avg_items:.1f}个活动，可能超过4个")
    elif pace == "intensive" and avg_items < 3:
        warnings.append(f"当前偏紧凑但每天平均{avg_items:.1f}个活动，可能少于3个")

    return errors, warnings


# 获取当前分支需要校验的行程数据。
def _itinerary_for_validation(state: TravelAgentState) -> tuple[list, str]:
    if get_plan_mode(state) == "replan":
        return get_draft_daily_itinerary(state), "draft_daily_itinerary"
    return get_daily_itinerary(state), "daily_itinerary"


# 检查预算结构是否完整。
def _validate_budget(budget: dict) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    if not budget:
        errors.append("budget is empty")
        return errors, warnings

    total = budget.get("total", 0)
    if total is None:
        errors.append("budget.total is missing")
    elif float(total) < 0:
        errors.append(f"budget.total is negative: {total}")

    errors.extend(_check_budget_consistency(budget))
    if not budget.get("saving_tips"):
        warnings.append("budget.saving_tips is empty")
    return errors, warnings


# 根据硬校验问题数量计算基础结构分。
def _hard_score(errors: list[str], warnings: list[str]) -> int:
    return max(0, 100 - len(errors) * 20 - len(warnings) * 5)


# 构造软评估 LLM 使用的上下文。
def _soft_evaluation_payload(
    state: TravelAgentState,
    itinerary: list,
    hard_warnings: list[str],
    field_name: str,
) -> Dict[str, Any]:
    return {
        "field_name": field_name,
        "destination": get_destination(state),
        "duration": get_duration(state),
        "plan_mode": get_plan_mode(state),
        "pace": get_pace(state),
        "budget_level": get_budget_level(state),
        "preferences": get_structured_preferences(state),
        "weather_info": state.get("weather_info"),
        "fetched_attractions": state.get("fetched_attractions"),
        "hard_warnings": hard_warnings,
        "itinerary": itinerary,
    }


# 构造要求 LLM 对行程质量进行软评分的消息。
def _build_soft_evaluation_messages(
    state: TravelAgentState,
    itinerary: list,
    hard_warnings: list[str],
    field_name: str,
) -> list[Any]:
    system_prompt = f"""
你是 TravelMate 的 Validator Agent，负责对已经通过硬校验的行程做软评估。
请只返回 JSON，不要返回 Markdown 或额外解释。
评分范围为 0-100，{SOFT_SCORE_THRESHOLD} 分及以上才可以放行。

JSON schema:
{{
  "score": 0,
  "passed": true,
  "reason": "一句话说明整体质量判断",
  "issues": ["影响体验或质量的主要问题"],
  "suggestions": ["下一轮修正时给 Itinerary Agent 的具体建议"]
}}

评估维度：
- 行程是否符合目的地、天数、节奏、偏好和出行人数。
- 每天安排是否自然、顺路、强度合理，午晚餐和休息是否得当。
- 景点/活动是否有明显重复、空泛、不可执行或与天气/景点数据冲突。
- REPLAN 模式下是否尊重已生效行程上下文，避免无谓大改。
- 不要因为轻微 warning 直接给低分；只有明显影响体验或可执行性时才扣到阈值以下。
""".strip()
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=json.dumps(
                _soft_evaluation_payload(state, itinerary, hard_warnings, field_name),
                ensure_ascii=False,
            )
        ),
    ]


# 将任意分数规范化为 0-100 的整数。
def _normalize_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


# 将 LLM 软评估响应规范化为稳定结构。
def _normalize_soft_evaluation(raw: Dict[str, Any]) -> Dict[str, Any]:
    score = _normalize_score(raw.get("score"))
    issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    suggestions = raw.get("suggestions") if isinstance(raw.get("suggestions"), list) else []
    return {
        "score": score,
        "threshold": SOFT_SCORE_THRESHOLD,
        "passed": score >= SOFT_SCORE_THRESHOLD,
        "model_passed": bool(raw.get("passed")),
        "reason": str(raw.get("reason") or "").strip(),
        "issues": [str(item) for item in issues],
        "suggestions": [str(item) for item in suggestions],
    }


# 调用 LLM 完成行程软评估，异常时返回不通过结果。
async def _run_soft_evaluation(
    state: TravelAgentState,
    itinerary: list,
    hard_warnings: list[str],
    field_name: str,
) -> Dict[str, Any]:
    try:
        llm = get_validator_llm()
        response = await call_llm(
            llm,
            _build_soft_evaluation_messages(state, itinerary, hard_warnings, field_name),
        )
        raw = ensure_dict(extract_json(message_content(response)), "soft evaluation response")
        return _normalize_soft_evaluation(raw)
    except Exception as exc:
        logger.exception("LLM soft evaluation failed")
        return {
            "score": 0,
            "threshold": SOFT_SCORE_THRESHOLD,
            "passed": False,
            "reason": "LLM 软评估失败",
            "issues": [str(exc)],
            "suggestions": ["保持原有硬校验通过结构，重新生成更稳定的行程草稿"],
        }

# 根据当前错误、分数和计数器判断是否应停止工作流。
def _should_stop_validation(
    passed: bool,
    attempts: int,
    hard_attempts: int,
    soft_attempts: int,
    soft_evaluation: Dict[str, Any] | None,
) -> bool:
    if passed:
        return True
    if attempts >= MAX_VALIDATION_ATTEMPTS:
        return True
    if hard_attempts >= MAX_HARD_VALIDATION_ATTEMPTS and soft_evaluation is None:
        return True
    return bool(soft_evaluation and soft_attempts >= MAX_SOFT_VALIDATION_ATTEMPTS)


# 遍历已注册处理器并收集需要用户决策的中断请求。
def _collect_user_decision_requests(state: TravelAgentState) -> list[Dict[str, Any]]:
    requests = []
    for interrupt_type, handler_cls in _handler_registry.items():
        try:
            handler = handler_cls()
            if not handler.should_trigger(state):
                continue

            payload = handler.build_payload(state)
            if not isinstance(payload, dict):
                raise ValueError("interrupt handler payload must be a dictionary")

            request = dict(payload)
            request.setdefault("type", interrupt_type)
            request["interrupt_type"] = interrupt_type
            requests.append(request)
        except Exception:
            logger.exception("Interrupt handler failed: type=%s", interrupt_type)
    return requests


# 触发用户决策中断，并兼容单个和多个处理器同时命中。
def _request_user_decision(requests: list[Dict[str, Any]]) -> Any:
    if len(requests) == 1:
        logger.info("Requesting user decision: type=%s", requests[0]["interrupt_type"])
        return interrupt(requests[0])

    logger.info("Requesting user decisions: count=%s", len(requests))
    return interrupt(
        {
            "type": "multiple_user_decisions",
            "title": "需要确认多个规划事项",
            "interrupts": requests,
        }
    )


# 根据当前路由分支执行对应的输出校验。
async def validator_node(state: TravelAgentState) -> Dict[str, Any]:
    budget = get_budget(state)
    attempts = get_validation_attempts(state) + 1
    hard_attempts = get_hard_validation_attempts(state) + 1
    soft_attempts = get_soft_validation_attempts(state)
    branch = state.get("next_node")

    errors = []
    warnings = []
    hard_errors = []
    hard_warnings = []
    itinerary = []
    itinerary_field = "daily_itinerary"
    soft_evaluation = None

    if branch == "budget_agent":
        hard_errors, hard_warnings = _validate_budget(budget)
    else:
        itinerary, itinerary_field = _itinerary_for_validation(state)
        hard_errors, hard_warnings = _validate_itinerary(itinerary, state, itinerary_field)

    errors.extend(hard_errors)
    warnings.extend(hard_warnings)

    if branch != "budget_agent" and not hard_errors:
        if soft_attempts >= MAX_SOFT_VALIDATION_ATTEMPTS:
            soft_evaluation = {
                "score": 0,
                "threshold": SOFT_SCORE_THRESHOLD,
                "passed": False,
                "reason": "软评估次数已达到上限，跳过本轮 LLM 调用",
                "issues": ["soft validation retry limit reached"],
                "suggestions": ["停止继续自动重试，保留当前校验报告供人工或前端处理"],
                "skipped": True,
            }
        else:
            soft_attempts += 1
            soft_evaluation = await _run_soft_evaluation(
                state,
                itinerary,
                hard_warnings,
                itinerary_field,
            )

        if not soft_evaluation["passed"]:
            errors.append(
                f"soft_score_below_threshold: {soft_evaluation['score']} < {soft_evaluation['threshold']}"
            )

    passed = not errors
    hard_score = _hard_score(hard_errors, hard_warnings)
    final_score = hard_score if soft_evaluation is None else min(hard_score, soft_evaluation["score"])
    stopped_by_guard = _should_stop_validation(
        passed,
        attempts,
        hard_attempts,
        soft_attempts,
        soft_evaluation,
    )
    logger.info("Validation attempt=%s branch=%s passed=%s errors=%s", attempts, branch, passed, errors)
    update: Dict[str, Any] = {
        "validation_attempts": attempts,
        "hard_validation_attempts": hard_attempts,
        "soft_validation_attempts": soft_attempts,
        "validation_report": {
            "errors": errors,
            "warnings": warnings,
            "score": final_score,
            "passed": passed,
            "hard_validation": {
                "attempts": hard_attempts,
                "passed": not hard_errors,
                "errors": hard_errors,
                "warnings": hard_warnings,
                "score": hard_score,
            },
            "soft_evaluation": soft_evaluation,
            "stopped_by_guard": stopped_by_guard,
            "retry_limits": {
                "max_total": MAX_VALIDATION_ATTEMPTS,
                "max_hard": MAX_HARD_VALIDATION_ATTEMPTS,
                "max_soft": MAX_SOFT_VALIDATION_ATTEMPTS,
            },
        },
        "is_finished": passed or stopped_by_guard,
    }
    if branch != "budget_agent" and get_plan_mode(state) == "replan" and passed:
        update["daily_itinerary"] = get_draft_daily_itinerary(state)
        update["draft_daily_itinerary"] = None
    if passed:
        user_decision_requests = _collect_user_decision_requests({**state, **update})
        if user_decision_requests:
            update["validation_report"]["user_decision_requests"] = user_decision_requests
            _request_user_decision(user_decision_requests)
    return update
