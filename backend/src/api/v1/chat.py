"""AI 对话与行程生成接口。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.exceptions import AppException
from src.graph.graph import get_graph_async

router = APIRouter(prefix="/chat")
logger = logging.getLogger("travelmate.api.chat")


class BudgetInput(BaseModel):
    """结构化输入中的预算约束。"""

    level: Literal["economy", "mid", "luxury"]
    min_total: Optional[float] = Field(default=None, ge=0)
    max_total: Optional[float] = Field(default=None, ge=0)

    # 检查预算上下限的数值关系。
    @model_validator(mode="after")
    def validate_range(self) -> "BudgetInput":
        if self.min_total is not None and self.max_total is not None:
            if self.min_total > self.max_total:
                raise ValueError("budget.min_total must not exceed budget.max_total")
        return self


class StructuredInput(BaseModel):
    """对话请求中的结构化旅行偏好。"""

    destination: str = Field(min_length=1)
    origin: Optional[str] = None
    start_date: Optional[str] = None
    duration: int = Field(gt=0)
    budget: BudgetInput
    hotel_preference: Optional[Literal["economy", "mid", "luxury"]] = None
    intercity_transport: List[
        Literal["flight", "high_speed_rail", "train", "coach", "self_driving"]
    ] = Field(default_factory=list)
    local_transport: List[
        Literal["metro", "bus", "taxi", "self_driving", "bike", "walking"]
    ] = Field(default_factory=list)
    pace: Literal["intensive", "relaxed"] = "relaxed"
    interests: List[
        Literal["history", "culture", "food", "nature", "shopping", "art", "nightlife"]
    ] = Field(default_factory=list)
    travelers: Optional[int] = Field(default=None, gt=0)
    travelers_type: Literal["adult", "family", "senior"] = "adult"


class ChatStreamRequest(BaseModel):
    """发起或继续对话的请求体。"""

    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    current_time: Optional[str] = None
    structured_input: Optional[StructuredInput] = None

    # 清理用户输入中的首尾空白。
    @field_validator("thread_id", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class UserDecision(BaseModel):
    """恢复中断流程时提交的用户决策。"""

    action: str
    hint: Optional[str] = None
    note: Optional[str] = None


class ResumeRequest(BaseModel):
    """恢复中断流程的请求体。"""

    thread_id: str = Field(min_length=1)
    user_decision: UserDecision


@dataclass
class ActiveRun:
    """记录一个正在执行的 graph 流程。"""

    thread_id: str
    user_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task] = None
    stop_requested: bool = False
    partial_tokens: int = 0
    has_partial_result: bool = False


_active_runs: Dict[str, ActiveRun] = {}


# 将任意 graph 数据转换为可写入 SSE 的 JSON 数据。
def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "type") and hasattr(value, "content"):
        return {
            "type": value.type,
            "content": _jsonable(value.content),
        }
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# 将事件名称和数据编码为 Server-Sent Events 消息。
def _sse(event: str, data: Any) -> str:
    payload = json.dumps(_jsonable(data), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


# 返回当前 UTC 时间的 ISO 8601 文本。
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# 将结构化表单转换为 TravelAgentState 使用的字段。
def _structured_state_values(structured_input: Optional[StructuredInput]) -> Dict[str, Any]:
    if structured_input is None:
        return {}

    preferences = {
        "budget_level": structured_input.budget.level,
        "budget_min_total": structured_input.budget.min_total,
        "budget_max_total": structured_input.budget.max_total,
        "hotel_preference": structured_input.hotel_preference or structured_input.budget.level,
        "intercity_transport": structured_input.intercity_transport,
        "local_transport": structured_input.local_transport,
        "pace": structured_input.pace,
        "interests": structured_input.interests,
        "travelers": structured_input.travelers or 1,
        "travelers_type": structured_input.travelers_type,
    }
    return {
        "destination": structured_input.destination,
        "origin": structured_input.origin,
        "start_date": structured_input.start_date,
        "duration": structured_input.duration,
        "structured_preferences": preferences,
    }


# 构造首次运行 graph 所需的完整 State。
def _initial_state(request: ChatStreamRequest, user_id: str) -> Dict[str, Any]:
    structured_values = _structured_state_values(request.structured_input)
    return {
        "messages": [HumanMessage(content=request.message)],
        "user_id": user_id,
        "thread_id": request.thread_id,
        "destination": structured_values.get("destination"),
        "origin": structured_values.get("origin"),
        "start_date": structured_values.get("start_date"),
        "duration": structured_values.get("duration"),
        "structured_preferences": structured_values.get("structured_preferences"),
        "weather_info": None,
        "fetched_attractions": None,
        "daily_itinerary": None,
        "budget": None,
        "draft_daily_itinerary": None,
        "draft_budget": None,
        "plan_mode": "plan",
        "current_mode": "plan",
        "current_time": request.current_time,
        "validation_attempts": 0,
        "hard_validation_attempts": 0,
        "soft_validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
        "deleted_at": None,
        "next_node": None,
    }


# 构造已有会话继续运行时提交给 graph 的增量 State。
def _continuation_input(request: ChatStreamRequest) -> Dict[str, Any]:
    values: Dict[str, Any] = {
        "messages": [HumanMessage(content=request.message)],
    }
    if request.current_time is not None:
        values["current_time"] = request.current_time
    values.update(_structured_state_values(request.structured_input))
    return values


# 创建 LangGraph 使用的 thread 配置。
def _thread_config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


# 获取应用复用的 graph 实例。
async def _get_graph() -> Any:
    return await get_graph_async()


# 获取指定会话的 checkpoint State，不存在时返回 None。
async def _get_snapshot(graph: Any, thread_id: str) -> Any:
    return await graph.aget_state(_thread_config(thread_id))


# 校验会话是否存在，并确认当前用户拥有该会话。
def _ensure_owner(snapshot: Any, user_id: str, thread_id: str) -> Dict[str, Any]:
    values = getattr(snapshot, "values", None) or {}
    if not values:
        raise AppException(
            code=40401,
            message="会话不存在",
            status_code=404,
            details={"thread_id": thread_id, "error": "未找到该会话记录"},
        )
    if values.get("deleted_at"):
        raise AppException(
            code=40401,
            message="会话不存在",
            status_code=404,
            details={"thread_id": thread_id, "error": "该会话已被删除"},
        )
    owner_id = values.get("user_id")
    if owner_id and owner_id != user_id:
        raise AppException(
            code=40301,
            message="无权操作该会话",
            status_code=403,
            details={"error": "当前用户与会话创建者不匹配"},
        )
    return values


# 检查用户决策字段并转换为 LangGraph resume 值。
def _validate_decision(decision: UserDecision) -> Dict[str, Any]:
    if decision.action not in {"accept", "modify", "reject"}:
        raise AppException(
            code=40006,
            message="决策类型无效",
            status_code=400,
            details={
                "field": "user_decision.action",
                "error": "允许值: accept, modify, reject",
            },
        )
    if decision.action == "modify" and not (decision.hint or "").strip():
        raise AppException(
            code=40005,
            message="修改操作缺少具体指令",
            status_code=400,
            details={
                "field": "user_decision.hint",
                "error": "当 action 为 modify 时，hint 为必填字段",
            },
        )
    return {
        "action": decision.action,
        "hint": decision.hint.strip() if decision.hint else None,
        "note": decision.note.strip() if decision.note else None,
    }


# 判断 checkpoint 是否包含 LangGraph 的中断任务。
def _has_interrupt(snapshot: Any) -> bool:
    for task in getattr(snapshot, "tasks", ()) or ():
        if getattr(task, "interrupts", None):
            return True
    return False


# 将 graph 更新转换成可供前端消费的节点事件。
def _node_event(thread_id: str, update: Any) -> Dict[str, Any]:
    if isinstance(update, dict) and len(update) == 1:
        node, data = next(iter(update.items()))
        return {
            "thread_id": thread_id,
            "node": node,
            "data": _jsonable(data),
        }
    return {
        "thread_id": thread_id,
        "node": None,
        "data": _jsonable(update),
    }


# 估算已经产生的文本 token 数，用于停止接口的统计字段。
def _estimate_tokens(data: Any) -> int:
    text = json.dumps(_jsonable(data), ensure_ascii=False)
    return max(1, len(text) // 4)


# 异步执行 graph，并把节点更新写入当前 SSE 队列。
async def _run_graph(
    run: ActiveRun,
    graph: Any,
    graph_input: Any,
    config: Dict[str, Any],
) -> None:
    try:
        async for update in graph.astream(graph_input, config=config, stream_mode="updates"):
            if run.stop_requested:
                break
            event = _node_event(run.thread_id, update)
            run.partial_tokens += _estimate_tokens(event)
            run.has_partial_result = True
            await run.queue.put(("node", event))

        if run.stop_requested:
            await run.queue.put(
                (
                    "stopped",
                    {
                        "thread_id": run.thread_id,
                        "stopped_at": _utc_now(),
                        "partial_tokens": run.partial_tokens,
                        "has_partial_result": run.has_partial_result,
                        "tip": "已为您保留当前已生成的部分行程，可继续修改或重新生成",
                    },
                )
            )
        else:
            snapshot = await graph.aget_state(config)
            await run.queue.put(
                (
                    "done",
                    {
                        "thread_id": run.thread_id,
                        "state": _jsonable(getattr(snapshot, "values", {})),
                    },
                )
            )
    except asyncio.CancelledError:
        run.stop_requested = True
        await run.queue.put(
            (
                "stopped",
                {
                    "thread_id": run.thread_id,
                    "stopped_at": _utc_now(),
                    "partial_tokens": run.partial_tokens,
                    "has_partial_result": run.has_partial_result,
                    "tip": "已为您保留当前已生成的部分行程，可继续修改或重新生成",
                },
            )
        )
    except Exception as exc:
        logger.exception("Graph stream failed for thread_id=%s", run.thread_id)
        await run.queue.put(
            (
                "error",
                {
                    "code": 50301,
                    "message": "AI 服务暂时不可用，请稍后重试",
                    "details": {"error": str(exc)},
                },
            )
        )
    finally:
        await run.queue.put(("close", None))


# 将 ActiveRun 的事件队列包装成 SSE 流响应。
async def _event_stream(run: ActiveRun):
    try:
        while True:
            event, data = await run.queue.get()
            if event == "close":
                break
            yield _sse(event, data)
    finally:
        if run.task and not run.task.done():
            run.stop_requested = True
            run.task.cancel()
        if _active_runs.get(run.thread_id) is run:
            _active_runs.pop(run.thread_id, None)


# 启动一次新的 graph 流程并返回 SSE 流。
@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    user_id: str = Header(..., alias="X-User-Id"),
):
    if request.thread_id in _active_runs:
        raise AppException(
            code=40902,
            message="当前会话正在生成",
            status_code=409,
            details={"thread_id": request.thread_id},
        )

    try:
        graph = await _get_graph()
        snapshot = await _get_snapshot(graph, request.thread_id)
        existing_values = getattr(snapshot, "values", None) or {}
        if existing_values:
            _ensure_owner(snapshot, user_id, request.thread_id)
            graph_input: Any = _continuation_input(request)
        else:
            graph_input = _initial_state(request, user_id)
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Unable to prepare chat stream")
        raise AppException(
            code=50301,
            message="AI 服务暂时不可用，请稍后重试",
            status_code=503,
            details={"error": str(exc)},
        ) from exc

    run = ActiveRun(thread_id=request.thread_id, user_id=user_id)
    _active_runs[request.thread_id] = run
    run.task = asyncio.create_task(
        _run_graph(run, graph, graph_input, _thread_config(request.thread_id))
    )
    return StreamingResponse(
        _event_stream(run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 停止指定会话正在执行的 graph 流程。
@router.post("/stop/{thread_id}")
async def stop_chat(
    thread_id: str,
    user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    run = _active_runs.get(thread_id)
    if run is None:
        raise AppException(
            code=40401,
            message="会话不存在",
            status_code=404,
            details={"thread_id": thread_id, "error": "当前会话没有正在生成"},
        )

    if user_id and run.user_id != user_id:
        raise AppException(
            code=40301,
            message="无权操作该会话",
            status_code=403,
            details={"error": "当前用户与会话创建者不匹配"},
        )

    run.stop_requested = True
    if run.task and not run.task.done():
        run.task.cancel()

    return {
        "code": 200,
        "message": "生成已终止",
        "data": {
            "thread_id": thread_id,
            "stopped_at": _utc_now(),
            "partial_tokens": run.partial_tokens,
            "has_partial_result": run.has_partial_result,
            "tip": "已为您保留当前已生成的部分行程，可继续修改或重新生成",
        },
    }


# 恢复处于 LangGraph interrupt 状态的会话并返回后续 SSE 流。
@router.post("/resume")
async def resume_chat(
    request: ResumeRequest,
    user_id: str = Header(..., alias="X-User-Id"),
):
    if request.thread_id in _active_runs:
        raise AppException(
            code=40902,
            message="当前会话正在生成",
            status_code=409,
            details={"thread_id": request.thread_id},
        )

    decision = _validate_decision(request.user_decision)
    try:
        graph = await _get_graph()
        snapshot = await _get_snapshot(graph, request.thread_id)
        values = _ensure_owner(snapshot, user_id, request.thread_id)
        if values.get("is_finished") or not _has_interrupt(snapshot):
            raise AppException(
                code=40901,
                message="当前会话不在中断状态，无需恢复",
                status_code=409,
                details={
                    "error": "Agent 流程已完成或尚未暂停，请检查当前状态后再调用恢复接口"
                },
            )
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Unable to prepare chat resume")
        raise AppException(
            code=50301,
            message="AI 服务暂时不可用，请稍后重试",
            status_code=503,
            details={"error": str(exc)},
        ) from exc

    run = ActiveRun(thread_id=request.thread_id, user_id=user_id)
    _active_runs[request.thread_id] = run
    run.task = asyncio.create_task(
        _run_graph(
            run,
            graph,
            Command(resume=decision),
            _thread_config(request.thread_id),
        )
    )
    return StreamingResponse(
        _event_stream(run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
