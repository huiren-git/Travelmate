"""AI 对话与行程生成接口。"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.core.exceptions import AppException
from src.graph.graph import get_graph_async
from src.models.chat import (
    ChatStreamRequest,
    LogisticsConfirmationRequest,
    ResumeRequest,
    StopChatData,
    UserDecision,
)
from src.models.common import ApiResponse
from src.utils.preferences_parser import parse_structured_preferences
from src.services.travel_logistics import confirm_logistics_item
from src.handlers.registry import get_handler

from src.core.tracing import set_trace_id, generate_trace_id, get_trace_id
from src.services.tracing_db import start_trace, end_trace

router = APIRouter(prefix="/chat")
logger = logging.getLogger("travelmate.api.chat")


@dataclass
class ActiveRun:
    """记录一个正在执行的 graph 流程。"""
    # thr_{16位短码}
    thread_id: str
    user_id: str
    trace_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: Optional[asyncio.Task] = None
    stop_requested: bool = False
    partial_tokens: int = 0
    has_partial_result: bool = False


_active_runs: Dict[str, ActiveRun] = {}


# 将任意 graph 数据转换为可写入 SSE 的 JSON 数据。
async def _store_user_decision_memory(
    user_id: str,
    thread_id: str,
    decision: Dict[str, Any],
) -> None:
    try:
        from src.services.memory_manager import add_memory

        action = str(decision.get("action") or "").strip()
        hint = str(decision.get("hint") or "").strip()
        note = str(decision.get("note") or "").strip()
        parts = [f"用户在会话 {thread_id} 中选择：{action}"]
        if hint:
            parts.append(f"修改要求：{hint}")
        if note:
            parts.append(f"备注：{note}")
        await add_memory(
            user_id=user_id,
            text="；".join(parts),
            memory_type="action",
            metadata={
                "source": "chat_resume",
                "thread_id": thread_id,
                "decision_action": action,
            },
        )
    except Exception:
        logger.exception("Failed to store user decision memory")


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


# 把 LangGraph 的 PregelTask 列表转成可 JSON 序列化的结构（PregelTask/Interrupt 无 model_dump，
# 原 _jsonable 会退化为 str，导致前端拿不到中断）。仅抽取前端需要的 id/name/interrupts.value。
def _serialize_interrupts(tasks: Any) -> list:
    result: list = []
    for task in tasks or []:
        interrupts = []
        for it in getattr(task, "interrupts", ()) or ():
            interrupts.append(
                {
                    "id": getattr(it, "id", None) or getattr(it, "interrupt_id", None),
                    "value": _jsonable(getattr(it, "value", None)),
                }
            )
        result.append(
            {
                "id": getattr(task, "id", None),
                "name": getattr(task, "name", None),
                "interrupts": interrupts,
            }
        )
    return result


# 将事件名称和数据编码为 Server-Sent Events 消息。
def _sse(event: str, data: Any) -> str:
    payload = json.dumps(_jsonable(data), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


# 返回当前 UTC 时间的 ISO 8601 文本。
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# 将结构化表单转换为 TravelAgentState 使用的字段。
def _structured_state_values(structured_input) -> Dict[str, Any]:
    if structured_input is None:
        return {}

    raw = (
        structured_input.model_dump()
        if hasattr(structured_input, "model_dump")
        else structured_input
    )
    parsed = parse_structured_preferences(raw)
    if not parsed:
        return {}
    values: Dict[str, Any] = {"structured_preferences": parsed}
    # 把 start_date 提到顶层，供 _initial_state 的 start_date 字段直接读取
    if "start_date" in parsed:
        values["start_date"] = parsed["start_date"]
    if "origin" in parsed:
        values["origin"] = parsed["origin"]
    return values


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
        "travel_logistics": None,
        "budget_max_allowed": None,
        "budget_auto_retry": 0,
        "budget_dirty": False,
        "auto_reduce_budget": False,
        "draft_daily_itinerary": None,
        "draft_budget": None,
        "intent": "plan",
        "plan_mode": "plan",
        "current_mode": "plan",
        "current_time": request.current_time,
        "validation_attempts": 0,
        "hard_validation_attempts": 0,
        "soft_validation_attempts": 0,
        "validation_report": None,
        "is_finished": False,
        "terminal_status": "running",
        "failure_reason": None,
        "summary_text": None,
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


def _interrupt_type(snapshot: Any) -> Optional[str]:
    """从 checkpoint 任务中提取当前可恢复的中断类型。"""
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            value = getattr(item, "value", item)
            if isinstance(value, dict) and isinstance(value.get("type"), str):
                return value["type"]
            if isinstance(value, str):
                return "budget_overrun" if value == "budget_confirmation" else value
    return None


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
    """
    异步执行 LangGraph，并将节点更新推送到 SSE 队列。

    Args:
        run: 当前运行的上下文（含 trace_id、queue、stop_requested）
        graph: 编译后的 LangGraph 实例
        graph_input: 初始 State 输入
        config: LangGraph 的运行配置（含 thread_id 等）
    """
    try:
        # 1. 流式执行 Graph
        async for update in graph.astream(
            graph_input,
            config=config,
            stream_mode="updates",  # 仅获取节点更新（也可用 "values" 获取全量状态）
        ):
            # 2. 检查停止标志
            if run.stop_requested:
                logger.info(f"Graph 执行被用户停止: {run.trace_id}")
                break

            # 3. 将节点更新放入队列（SSE 会消费）
            await run.queue.put(("node", update))

        # 4. 获取最终状态快照（用于 "done" 事件）
        final_state = await graph.aget_state(config)
        snapshot = {
            "trace_id": run.trace_id,
            "values": final_state.values,
            "next": getattr(final_state, "next", ()),
            "tasks": _serialize_interrupts(getattr(final_state, "tasks", ())),
        }

        # 5. 根据是否被停止来决定最终状态
        if run.stop_requested:
            await end_trace(run.trace_id, status="cancelled")
            await run.queue.put(("stopped", {"trace_id": run.trace_id}))
        else:
            await end_trace(run.trace_id, status="success")
            await run.queue.put(("done", snapshot))

    except asyncio.CancelledError:
        # 6. 任务被显式取消（如客户端断开）
        logger.info(f"Graph 任务被取消: {run.trace_id}")
        await end_trace(run.trace_id, status="cancelled")
        run.stop_requested = True
        await run.queue.put(("stopped", {"trace_id": run.trace_id}))
        # 注意：不要重新抛出，让 finally 正常执行

    except Exception as exc:
        # 7. 业务异常（如 LLM 超时、JSON 解析失败等）
        logger.exception(f"Graph 执行异常: {run.trace_id} - {exc}")
        await end_trace(run.trace_id, status="error", error_msg=str(exc))
        await run.queue.put(("error", {"trace_id": run.trace_id, "error": str(exc)}))

    finally:
        # 8. 无论何种退出，都通知队列关闭（SSE 会收到 close 事件）
        await run.queue.put(("close", None))


# 将 ActiveRun 的事件队列包装成 SSE 流响应。
async def _event_stream(run: ActiveRun):
    try:
        while True:
            event, data = await run.queue.get()
            if event == "close":
                break
            yield _sse(event, data)
    except Exception as e:
        # 这里只处理 queue.get() 本身的异常（极小概率），直接记录日志即可
        logger.exception("SSE stream consumer error")
        raise
    finally:
        if run.task and not run.task.done():
            run.task.cancel()
        if _active_runs.get(run.thread_id) is run:
            _active_runs.pop(run.thread_id, None)

# 启动一次新的 graph 流程并返回 SSE 流。
@router.post("/logistics/confirm", response_model=ApiResponse[Dict[str, Any]])
async def confirm_logistics(
    request: LogisticsConfirmationRequest,
    user_id: str = Header(default="demo-user", alias="X-User-Id"),
):
    """确认城际交通或全程住宿方案，并写回当前会话状态。"""
    graph = await _get_graph()
    config = {"configurable": {"thread_id": request.thread_id}}
    snapshot = await graph.aget_state(config)
    values = getattr(snapshot, "values", {}) or {}
    logistics = values.get("travel_logistics")
    if not isinstance(logistics, dict):
        raise AppException(code=40002, message="参数校验失败", details={"item_key": "当前会话没有可确认的出行方案"})
    try:
        confirmed = confirm_logistics_item(logistics, request.item_key)
    except ValueError:
        raise AppException(code=40002, message="参数校验失败", details={"item_key": "未知的出行方案"})
    await graph.aupdate_state(config, {"travel_logistics": confirmed})
    return ApiResponse(code=200, message="ok", data=confirmed)


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    user_id: str = Header(..., alias="X-User-Id"),
):
    # 1. 检查当前会话是否已经在运行中，避免重复启动。
    if request.thread_id in _active_runs:
        raise AppException(
            code=40902,
            message="当前会话正在生成",
            status_code=409,
            details={"thread_id": request.thread_id},
        )

    # 2. 生成并设置 Trace ID
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    
    # 3. 将 trace_id 存入数据库（状态：running）
    await start_trace(
        trace_id=trace_id,
        thread_id=request.thread_id,
        user_id=user_id,
        input_message=request.message
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
    except AppException as e:
        # 4. 异常时更新 trace 状态为 error
        await end_trace(trace_id, status="error", error_msg=str(e))
        raise
    except Exception as e:
        await end_trace(trace_id, status="error", error_msg=str(e))
        logger.exception("Unable to prepare chat stream")
        raise AppException(
            code=50301,
            message="AI 服务暂时不可用，请稍后重试",
            status_code=503,
            details={"error": str(e)},
        ) from e

    run = ActiveRun(thread_id=request.thread_id, user_id=user_id, trace_id=trace_id)
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
@router.post("/stop/{thread_id}", response_model=ApiResponse[StopChatData])
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

    return ApiResponse(
        code=200,
        message="生成已终止",
        data=StopChatData(
            thread_id=thread_id,
            stopped_at=_utc_now(),
            partial_tokens=run.partial_tokens,
            has_partial_result=run.has_partial_result,
            tip="已为您保留当前已生成的部分行程，可继续修改或重新生成",
        ),
    )


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

    await _store_user_decision_memory(user_id, request.thread_id, decision)
    interrupt_type = _interrupt_type(snapshot)
    handler_update: Dict[str, Any] = {}
    if interrupt_type:
        try:
            handler_update = get_handler(interrupt_type).handle_resume(values, decision["action"], decision)
        except Exception as exc:
            logger.exception("Unable to handle resume decision: type=%s", interrupt_type)
            raise AppException(
                code=50301,
                message="恢复流程暂时不可用，请稍后重试",
                status_code=503,
                details={"error": str(exc)},
            ) from exc

    if decision["action"] == "modify" and interrupt_type == "budget_overrun":
        await graph.aupdate_state(
            _thread_config(request.thread_id),
            {
                **handler_update,
                "user_decision": decision,
                "intent": "replan",
                "plan_mode": "replan",
                "current_mode": "replan",
                "next_node": "itinerary_agent",
                "is_finished": False,
                "terminal_status": "running",
                "failure_reason": None,
            },
        )
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    await start_trace(
        trace_id=trace_id,
        thread_id=request.thread_id,
        user_id=user_id,
        input_message=f"恢复生成：{decision['action']}",
    )
    run = ActiveRun(thread_id=request.thread_id, user_id=user_id, trace_id = trace_id)
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
