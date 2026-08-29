"""Validator node for workflow output verification."""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from src.handlers.registry import _handler_registry
from src.handlers.budget_overrun_handler import BudgetOverrunHandler
from src.graph.state import TravelAgentState
from src.core.tracing import get_trace_id
from src.services.reference_trip_service import archive_reference_trip
from src.utils.llm_utils import call_llm, ensure_dict, extract_json, message_content
from src.utils.state_utils import (
    get_budget_level,
    get_budget,
    get_draft_budget,
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
SOFT_SCORE_THRESHOLD = 70


# 获取用于 Validator 的 LLM 实例，温度固定为 0.0
def get_validator_llm():
    """
    获取用于 Validator 的 LLM 实例，温度固定为 0.0
    """
    from src.agents.base import get_llm

    return get_llm(temperature=0.0)


# 获取用于生成定稿总结语的 LLM 实例，温度 0.7 以获得更有温度的文案。
def get_summary_llm():
    from src.agents.base import get_llm

    return get_llm(temperature=0.7)


# 收集每日行程的亮点景点名，供总结语 prompt 使用。
def _collect_daily_attraction_names(itinerary: list) -> list[Dict[str, Any]]:
    daily_attractions: list[Dict[str, Any]] = []
    for day in itinerary:
        if not isinstance(day, dict):
            continue
        names = [
            item.get("activity", "")
            for item in (day.get("items") or [])
            if isinstance(item, dict) and item.get("activity")
        ]
        daily_attractions.append({"day": day.get("day"), "attractions": names})
    return daily_attractions


# 构造要求 LLM 生成定稿总结语的消息列表。
def _build_summary_messages(
    state: TravelAgentState,
    itinerary: list,
    budget: Dict[str, Any],
) -> list[Any]:
    destination = get_destination(state)
    duration = get_duration(state)
    budget_level = get_budget_level(state)
    saving_tips = budget.get("saving_tips") if isinstance(budget, dict) else None
    daily_attractions = _collect_daily_attraction_names(itinerary)

    system_prompt = f"""你是 TravelMate 的行程文案撰写助手。请基于以下已定稿的行程信息，生成一段面向用户的总结语。

要求：
- 语气温暖、有感染力，像一位懂旅行的朋友在介绍这次旅程。
- 控制在 80-150 字以内，写成一段话，不要分点、不要使用 Markdown 符号。
- 自然地融入目的地、天数、每日亮点景点、预算等级和省钱小贴士。
- 不要逐天罗列所有景点，挑每天的亮点即可。
- 不要出现"总结语""文案""好的"等元描述或寒暄，直接输出文案本身。

行程信息：
- 目的地：{destination}
- 天数：{duration}
- 预算等级：{budget_level}
- 每日景点：{json.dumps(daily_attractions, ensure_ascii=False)}
- 省钱建议：{json.dumps(saving_tips, ensure_ascii=False) if saving_tips else "无"}
""".strip()

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content="请生成这次行程的总结语。"),
    ]


# 调用 LLM 生成定稿后的总结语文案，异常时返回 None 不影响主流程。
async def _generate_summary_text(
    state: TravelAgentState,
    itinerary: list,
    budget: Dict[str, Any],
) -> Optional[str]:
    try:
        llm = get_summary_llm()
        response = await call_llm(llm, _build_summary_messages(state, itinerary, budget))
        text = message_content(response).strip()
        return text or None
    except Exception:
        logger.exception("Failed to generate summary_text")
        return None


# 出发日期未由用户在结构化表单（或对话）中显式指定时，系统默认从明天开始规划。
# 为避免“默认今天导致首日活动过早、被时间锁标为已完成”的困惑，在首条行程总结语后
# 追加一句提示，告知默认起点与修改入口。仅在 PLAN 模式的首次生成（尚无行程）时追加。
def _default_start_date_hint(state: TravelAgentState) -> Optional[str]:
    if state.get("start_date") is not None:
        return None
    if get_plan_mode(state) != "plan":
        return None
    if get_daily_itinerary(state):
        # 非首次生成（已有行程），不再重复提示
        return None
    tomorrow = date.today() + timedelta(days=1)
    formatted = f"{tomorrow.year}年{tomorrow.month}月{tomorrow.day}日"
    return (
        f"\n\n（已为你从明天（{formatted}）开始规划。"
        f"如需指定出发日期，可在「计划清单」中调整。）"
    )


# 把行程压平成 {date: {time: activity}}，用于比较 REPLAN 前后差异。
def _itinerary_index(itinerary: list) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for day in itinerary or []:
        if not isinstance(day, dict):
            continue
        date_text = str(day.get("date") or "")
        for item in day.get("items") or []:
            if isinstance(item, dict):
                index.setdefault(date_text, {})[str(item.get("time") or "")] = str(item.get("activity") or "")
    return index


# 计算 REPLAN 前后的实际变化，供反馈语描述“到底改了什么”。
def _diff_itinerary(old: list, new: list) -> Dict[str, Any]:
    old_index, new_index = _itinerary_index(old), _itinerary_index(new)
    removed, added, replaced, changed_dates = [], [], [], []
    for date_text in sorted(set(old_index) | set(new_index)):
        old_day, new_day = old_index.get(date_text, {}), new_index.get(date_text, {})
        if old_day == new_day:
            continue
        changed_dates.append(date_text)
        old_names, new_names = set(old_day.values()), set(new_day.values())
        for time_text, activity in old_day.items():
            if activity in new_names:
                continue
            counterpart = new_day.get(time_text)
            if counterpart and counterpart not in old_names:
                replaced.append({"date": date_text, "time": time_text, "from": activity, "to": counterpart})
            else:
                removed.append({"date": date_text, "time": time_text, "activity": activity})
        for time_text, activity in new_day.items():
            if activity in old_names:
                continue
            if any(e["date"] == date_text and e["to"] == activity for e in replaced):
                continue
            added.append({"date": date_text, "time": time_text, "activity": activity})
    return {"changed_dates": changed_dates, "replaced": replaced, "removed": removed,
            "added": added, "empty": not (replaced or removed or added)}


# LLM 不可用时的确定性兜底文案，避免前端退化成“行程已生成，已同步到计划面板。”
def _fallback_replan_feedback(changes: Dict[str, Any]) -> str:
    if changes.get("empty"):
        return "这次没有改动你的行程，可能相关时段已经过去或不在本次行程范围内，你可以再告诉我想调整哪一天。"
    parts = [f"把「{e['from']}」换成了「{e['to']}」" for e in changes.get("replaced", [])[:3]]
    parts += [f"取消了「{e['activity']}」" for e in changes.get("removed", [])[:2]]
    parts += [f"新增了「{e['activity']}」" for e in changes.get("added", [])[:2]]
    return "已按你的要求调整：" + "，".join(parts) + "，其余安排保持不变。"


# 构造要求 LLM 生成 REPLAN 反馈语的消息。
def _build_replan_feedback_messages(
    state: TravelAgentState,
    changes: Dict[str, Any],
    itinerary: list,
) -> list[Any]:
    scope = state.get("replan_scope") or {}
    instruction = str(scope.get("instruction") or "").strip()
    scope_brief = {key: value for key, value in scope.items() if key != "instruction"}
    system_prompt = f"""你是 TravelMate 的行程调整反馈助手。用户刚提出了一条调整行程的指令，行程已按指令改好。
请写一段面向用户的确认反馈。

要求：
- 直接回应用户这句指令，说清「改了什么」以及「改完之后的体验是什么样」。
- 只描述 changes 里真实发生的变化；changes.empty 为 true 时，坦诚说明本轮没有改动及原因。
- 不要写成行程总结语，不要罗列整段行程，不要逐天复述景点。
- 不要出现"系统""后端""字段"等技术词，也不要"好的""以下是"这类寒暄和元描述。
- 60-120 字，一段话，不要 Markdown，不要分点。

用户指令：{instruction or "（未捕获到原始指令）"}
授权范围：{json.dumps(scope_brief, ensure_ascii=False)}
实际变化：{json.dumps(changes, ensure_ascii=False)}
调整后各天亮点：{json.dumps(_collect_daily_attraction_names(itinerary), ensure_ascii=False)}
天气：{json.dumps(state.get("weather_info"), ensure_ascii=False)}
""".strip()
    return [SystemMessage(content=system_prompt), HumanMessage(content="请给出这次调整的反馈。")]


# 调用 LLM 生成 REPLAN 反馈语，异常时用确定性兜底文案。
async def _generate_replan_feedback_text(
    state: TravelAgentState,
    itinerary: list,
    changes: Dict[str, Any],
) -> str:
    try:
        llm = get_summary_llm()
        response = await call_llm(llm, _build_replan_feedback_messages(state, changes, itinerary))
        return message_content(response).strip() or _fallback_replan_feedback(changes)
    except Exception:
        logger.exception("Failed to generate replan feedback text")
        return _fallback_replan_feedback(changes)


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


def _validate_travel_logistics(state: TravelAgentState, logistics: Any) -> list[str]:
    """校验交通与全程住宿的费用、状态和高德字段是否自洽。"""
    if not isinstance(logistics, dict):
        return []
    errors: list[str] = []
    for leg in logistics.get("intercity_legs") or []:
        if not isinstance(leg, dict):
            errors.append("城际交通段格式错误")
            continue
        cost = float(leg.get("cost") or 0)
        if cost < 0:
            errors.append("城际交通费用不能为负数")
        if leg.get("status") == "pending" and cost != 0:
            errors.append("待补充的城际交通不得计入费用")
    hotel = logistics.get("accommodation")
    if isinstance(hotel, dict) and hotel.get("mode") != "home":
        nights, rooms, rate, cost = (float(hotel.get(key) or 0) for key in ("nights", "rooms", "nightly_rate", "cost"))
        if nights != max(1, get_duration(state) - 1):
            errors.append("住宿晚数与行程天数不一致")
        if abs(nights * rooms * rate - cost) > 0.01:
            errors.append("住宿费用与晚数、房间数及单晚价格不一致")
    for leg in logistics.get("local_transport_legs") or []:
        if not isinstance(leg, dict) or not leg.get("from_name") or not leg.get("to_name"):
            errors.append("市内交通段缺少起终点")
            continue
        if float(leg.get("cost") or 0) < 0:
            errors.append("市内交通费用不能为负数")
        if leg.get("estimate_source") == "amap" and (leg.get("distance_km") is None or leg.get("duration_minutes") is None):
            errors.append("高德市内交通段缺少距离或时长")
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
    if state.get("draft_daily_itinerary") is not None:
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


# 预算超支自动微调判定：5%-20% 区间且未达次数上限时返回 True，应自动削减行程而非中断用户。
def _budget_auto_retry_needed(state: TravelAgentState) -> bool:
    try:
        return BudgetOverrunHandler().should_auto_retry(state)
    except Exception:
        logger.exception("Budget auto-retry check failed")
        return False


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
    budget = get_draft_budget(state) if state.get("draft_budget") is not None else get_budget(state)
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
        hard_errors.extend(_validate_travel_logistics(state, state.get("travel_logistics")))
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
    should_run_budget_after_itinerary = (
        passed
        and branch == "itinerary_agent"
        # 任一行程草稿都要进入预算阶段；不能因已有正式预算而跳过对新草稿的预算校验。
        and state.get("draft_daily_itinerary") is not None
    )
    # 预算超支自动微调：5%-20% 区间且未达次数上限时，自动削减行程重算，不中断用户。
    # 仅在 budget_agent 分支（pass B，budget.total 已落库）判定，避免 pass A 用旧预算误触发。
    auto_retry = (
        passed
        and branch == "budget_agent"
        and _budget_auto_retry_needed(state)
    )
    logger.info("Validation attempt=%s branch=%s passed=%s errors=%s", attempts, branch, passed, errors)
    is_finished = (passed or stopped_by_guard) and not (should_run_budget_after_itinerary or auto_retry)
    terminal_status = "confirmed" if is_finished and passed else "failed" if is_finished else "running"
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
        "is_finished": is_finished,
        "terminal_status": terminal_status,
        "failure_reason": (
            "; ".join(errors) or "行程质量校验未通过，已停止自动重试"
        ) if terminal_status == "failed" else None,
    }
    if auto_retry:
        # 进入预算自动微调闭环：路由回 itinerary_agent 自行削减行程，递增计数器、置标记。
        update["next_node"] = "itinerary_agent"
        update["auto_reduce_budget"] = True
        update["budget_auto_retry"] = int(state.get("budget_auto_retry", 0)) + 1
        update["is_finished"] = False
    elif should_run_budget_after_itinerary:
        update["next_node"] = "budget_agent"
    if branch == "budget_agent" and passed and not auto_retry:
        # 偏好更新只重算交通/预算时没有行程草稿，必须保留已生效的每日安排。
        if state.get("draft_daily_itinerary") is not None:
            update["daily_itinerary"] = get_draft_daily_itinerary(state)
        update["budget"] = budget
        update["draft_daily_itinerary"] = None
        update["draft_budget"] = None
    if terminal_status == "confirmed" and final_score >= 85:
        try:
            await archive_reference_trip({**state, **update}, get_trace_id())
        except Exception:
            logger.exception("Reference trip archive failed")
    if passed and not auto_retry:
        user_decision_requests = _collect_user_decision_requests({**state, **update})
        if user_decision_requests:
            update["validation_report"]["user_decision_requests"] = user_decision_requests
            # 接住 interrupt() 在 resume 时回灌的用户决策（含 action/hint/note）。
            # 首次执行此处会暂停（interrupt 抛出），resume 后 validator_node 重入，
            # LangGraph 对“已 resume 的 interrupt”直接返回 resume 值不再二次暂停，
            # 故 decision 此刻可拿到值并写入 state，供下游 REPLAN 读取。不会死循环。
            decision = _request_user_decision(user_decision_requests)
            if decision:
                update["user_decision"] = decision
    # 定稿后生成当轮回复文案：validator_router 在 is_finished=True 时直通 __end__，
    # 故同一轮不会重复进入 validator，可安全地在每个完成轮重新生成。
    # 若上方触发了 user_decision interrupt，此处不会执行（interrupt 已抛出），等 resume 后重入再生成。
    # PLAN 模式生成行程总结语；REPLAN 模式基于 old(get_daily_itinerary(state)) vs
    # new(get_daily_itinerary(merged_state)) 的 diff 生成“指令反馈语”。
    # 二者都写入 summary_text（语义已放宽为“本轮回复文案”）与 messages，前端无需改动。
    if terminal_status == "confirmed":
        merged_state = {**state, **update}
        final_itinerary = get_daily_itinerary(merged_state)
        if get_plan_mode(state) == "replan":
            changes = _diff_itinerary(get_daily_itinerary(state), final_itinerary)
            update["replan_changes"] = changes
            reply_text = await _generate_replan_feedback_text(merged_state, final_itinerary, changes)
        else:
            reply_text = await _generate_summary_text(merged_state, final_itinerary, get_budget(merged_state))
        if reply_text:
            # 未显式指定出发日期时，于首条回复追加“默认明天”提示（方案②）
            hint = _default_start_date_hint(state)
            if hint:
                reply_text = reply_text + hint
            update["summary_text"] = reply_text
            update["messages"] = [AIMessage(content=reply_text)]
    return update
