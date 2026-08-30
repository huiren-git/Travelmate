"""行程会话管理接口。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, Query, Response

from src.api.v1.chat import _active_runs, _jsonable
from src.core.exceptions import (
    AppException,
    raise_database_unavailable,
    raise_forbidden_resource,
    raise_session_not_found,
    raise_validation_error,
)
from src.graph.graph import get_graph_async
from src.models.common import ApiResponse
from src.models.sessions import (
    SessionItem,
    SessionListData,
    SessionListResponse,
    SessionSnapshotData,
)
# 读取 snapshot 时按墙钟 now 实时推导行程项状态（仅把"默认 upcoming 且已过去"
# 的项覆写为 completed，不触碰显式 completed/ongoing）。复用 itinerary_agent 的纯函数，
# 避免重复逻辑。sessions 已通过 graph 间接加载 agents，无循环 import 风险。
from src.agents.itinerary_agent import _apply_time_based_status

router = APIRouter(prefix="/sessions")
logger = logging.getLogger("travelmate.api.sessions")


# 返回当前 UTC 时间的 ISO 8601 文本。
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# 创建 LangGraph 使用的 thread 配置。
def _thread_config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


# 获取应用复用的 graph 实例。
async def _get_graph() -> Any:
    return await get_graph_async()


# 获取指定会话的 checkpoint 快照。
async def _get_snapshot(graph: Any, session_id: str) -> Any:
    return await graph.aget_state(_thread_config(session_id))


# 从 LangGraph 配置中提取 thread_id。
def _thread_id_from_config(config: Any) -> Optional[str]:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    thread_id = configurable.get("thread_id")
    return str(thread_id) if thread_id else None


# 从 checkpoint 条目中提取 thread_id。
def _thread_id_from_checkpoint_tuple(item: Any) -> Optional[str]:
    return _thread_id_from_config(getattr(item, "config", None))


# 将 ISO 8601 时间文本解析成可比较的 datetime。
def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise_validation_error(
            details={"field": "cursor", "error": "cursor 必须是 ISO 8601 时间格式"}
        )
        raise AssertionError("unreachable") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# 将时间文本转换成列表排序使用的键。
def _datetime_sort_key(value: Optional[str]) -> datetime:
    parsed = _parse_iso_datetime(value)
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


# 判断一个 snapshot 是否包含有效 State。
def _has_values(snapshot: Any) -> bool:
    values = getattr(snapshot, "values", None)
    return isinstance(values, dict) and bool(values)


# 校验当前用户是否拥有指定会话。
def _ensure_owner(values: Dict[str, Any], user_id: Optional[str]) -> None:
    if user_id is None:
        return
    owner_id = values.get("user_id")
    if owner_id and owner_id != user_id:
        raise_forbidden_resource(details={"error": "当前用户与会话创建者不匹配"})


# 根据出发日期和完成标记推断行程状态。
def _session_status(values: Dict[str, Any]) -> Literal["planning", "confirmed", "completed", "failed", "deleted"]:
    if values.get("deleted_at"):
        return "deleted"
    if values.get("terminal_status") == "failed":
        return "failed"
    start_date = values.get("start_date")
    if isinstance(start_date, str):
        try:
            if date.fromisoformat(start_date) < date.today():
                return "completed"
        except ValueError:
            pass
    if values.get("is_finished"):
        return "confirmed"
    return "planning"


# 从 snapshot 中读取最后更新时间。
def _snapshot_last_updated(snapshot: Any) -> str:
    created_at = getattr(snapshot, "created_at", None)
    if isinstance(created_at, str) and created_at:
        return created_at.replace("+00:00", "Z")
    return _utc_now()


# 将 checkpoint State 转换为历史会话列表条目。
def _session_item_from_snapshot(thread_id: str, snapshot: Any) -> SessionItem:
    values = getattr(snapshot, "values", None) or {}
    return SessionItem(
        thread_id=thread_id,
        destination=values.get("destination"),
        start_date=values.get("start_date"),
        duration=values.get("duration"),
        status=_session_status(values),
        last_updated=_snapshot_last_updated(snapshot),
    )


# 生成当前 TravelMate 工作流的静态图结构。
def _graph_structure() -> Dict[str, Any]:
    return {
        "nodes": [
            "pre_fetcher",
            "supervisor",
            "itinerary_agent",
            "budget_agent",
            "validator",
        ],
        "edges": [
            {"from": "__start__", "to": "pre_fetcher"},
            {"from": "pre_fetcher", "to": "supervisor"},
            {"from": "supervisor", "to": "itinerary_agent"},
            {"from": "supervisor", "to": "budget_agent"},
            {"from": "supervisor", "to": "__end__"},
            {"from": "itinerary_agent", "to": "validator"},
            {"from": "budget_agent", "to": "validator"},
            {"from": "validator", "to": "itinerary_agent"},
            {"from": "validator", "to": "budget_agent"},
            {"from": "validator", "to": "__end__"},
        ],
    }


# 将 LangGraph task 转换为前端可展示的任务项。
def _task_item(task: Any) -> Dict[str, Any]:
    error = getattr(task, "error", None)
    interrupts = getattr(task, "interrupts", None) or ()
    result = getattr(task, "result", None)
    if error:
        status = "failed"
    elif interrupts:
        status = "interrupted"
    elif result is not None:
        status = "done"
    else:
        status = "pending"

    return {
        "id": str(getattr(task, "id", "")),
        "name": getattr(task, "name", None),
        "path": _jsonable(getattr(task, "path", None)),
        "status": status,
        "output": _jsonable(result),
        "error": str(error) if error else None,
        "interrupts": [
            {
                "id": getattr(item, "id", None) or getattr(item, "interrupt_id", None),
                "value": _jsonable(getattr(item, "value", item)),
            }
            for item in interrupts
        ],
    }


# 从 snapshot 中整理任务清单。
def _task_list(snapshot: Any) -> List[Dict[str, Any]]:
    tasks = getattr(snapshot, "tasks", None) or ()
    return [_task_item(task) for task in tasks]


# 从 snapshot 中整理元数据。
def _snapshot_metadata(snapshot: Any, include_raw_traces: bool) -> Dict[str, Any]:
    metadata = getattr(snapshot, "metadata", None) or {}
    values = getattr(snapshot, "values", None) or {}
    trace_logs = values.get("trace_logs") or metadata.get("trace_logs") or []
    return {
        "total_llm_calls": int(values.get("total_llm_calls") or metadata.get("total_llm_calls") or 0),
        "total_tokens_consumed": int(
            values.get("total_tokens_consumed") or metadata.get("total_tokens_consumed") or 0
        ),
        "trace_logs": _jsonable(trace_logs) if include_raw_traces else [],
    }


# 将 checkpoint 快照组装为说明书约定的快照响应。
def _snapshot_response(
    session_id: str,
    snapshot: Any,
    include_raw_traces: bool,
) -> SessionSnapshotData:
    values = getattr(snapshot, "values", None) or {}
    blackboard = _jsonable(values)
    # 读取时按墙钟 now 重新推导行程项状态：仅把"默认 upcoming 且已过去"的项覆写为
    # completed，不触碰显式 completed/ongoing（硬边界）。
    # _jsonable 已生成全新容器，此处 in-place 改写不会污染 checkpoint / 缓存。
    # datetime.now() 为服务器本地墙钟，与 _item_datetime 产出的本地 wall-clock 时间同帧。
    itinerary = blackboard.get("daily_itinerary") if isinstance(blackboard, dict) else None
    if isinstance(itinerary, list):
        _apply_time_based_status(itinerary, datetime.now())
    return SessionSnapshotData(
        session_id=session_id,
        state={
            "task_list": _task_list(snapshot),
            "blackboard": blackboard,
        },
        graph_structure=_graph_structure(),
        metadata=_snapshot_metadata(snapshot, include_raw_traces),
        created_at=_snapshot_last_updated(snapshot),
    )


# 枚举 checkpointer 中已经存在的 thread_id。
async def _list_thread_ids(graph: Any) -> List[str]:
    checkpointer = getattr(graph, "checkpointer", None)
    if checkpointer is None or not hasattr(checkpointer, "alist"):
        return []

    seen: set[str] = set()
    thread_ids: List[str] = []
    try:
        async for item in checkpointer.alist(None):
            thread_id = _thread_id_from_checkpoint_tuple(item)
            if thread_id and thread_id not in seen:
                seen.add(thread_id)
                thread_ids.append(thread_id)
    except Exception as exc:
        logger.exception("Unable to list session checkpoints")
        raise_database_unavailable(details={"error": str(exc)})

    return thread_ids


# 获取指定用户的所有会话列表项。
async def _list_user_session_items(graph: Any, user_id: str) -> List[SessionItem]:
    items: List[SessionItem] = []
    for thread_id in await _list_thread_ids(graph):
        snapshot = await _get_snapshot(graph, thread_id)
        if not _has_values(snapshot):
            continue
        values = getattr(snapshot, "values", None) or {}
        if values.get("user_id") != user_id:
            continue
        if values.get("deleted_at"):
            continue
        items.append(_session_item_from_snapshot(thread_id, snapshot))

    items.sort(key=lambda item: _datetime_sort_key(item.last_updated), reverse=True)
    return items


# 对会话列表执行游标分页。
def _paginate_sessions(
    items: List[SessionItem],
    limit: int,
    cursor: Optional[str],
) -> SessionListData:
    if limit > 50:
        raise_validation_error(details={"field": "limit", "error": "limit 不能超过 50"})

    cursor_dt = _parse_iso_datetime(cursor)
    if cursor_dt is not None:
        items = [
            item
            for item in items
            if _datetime_sort_key(item.last_updated) < cursor_dt
        ]

    page = items[:limit]
    has_more = len(items) > limit
    next_cursor = page[-1].last_updated if has_more and page else None
    return SessionListData(sessions=page, next_cursor=next_cursor, has_more=has_more)


# 将指定 thread 标记为逻辑删除。
async def _mark_thread_deleted(graph: Any, session_id: str) -> None:
    if not hasattr(graph, "aupdate_state"):
        raise_database_unavailable(details={"error": "当前 graph 不支持更新 thread 状态"})
    try:
        await graph.aupdate_state(
            _thread_config(session_id),
            {"deleted_at": _utc_now()},
            as_node="validator",
        )
    except Exception as exc:
        logger.exception("Unable to mark session checkpoint as deleted")
        raise_database_unavailable(details={"error": str(exc)})


# 返回指定会话的完整 checkpoint 快照。
@router.get("/{session_id}/snapshot", response_model=ApiResponse[SessionSnapshotData])
async def get_session_snapshot(
    session_id: str,
    include_raw_traces: bool = Query(default=False),
    user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    graph = await _get_graph()
    snapshot = await _get_snapshot(graph, session_id)
    if not _has_values(snapshot):
        raise_session_not_found(thread_id=session_id)

    values = getattr(snapshot, "values", None) or {}
    if values.get("deleted_at"):
        raise_session_not_found(thread_id=session_id)
    _ensure_owner(values, user_id)
    return ApiResponse(
        code=200,
        message="获取成功",
        data=_snapshot_response(session_id, snapshot, include_raw_traces),
    )


# 返回当前用户的历史行程会话列表。
@router.get("", response_model=SessionListResponse)
async def get_sessions(
    limit: int = Query(default=20, ge=1),
    cursor: Optional[str] = Query(default=None),
    user_id: str = Header(..., alias="X-User-Id"),
):
    graph = await _get_graph()
    items = await _list_user_session_items(graph, user_id)
    data = _paginate_sessions(items, limit, cursor)
    return SessionListResponse(code=200, message="获取成功", data=data)


# 删除指定会话的所有历史记录。
@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user_id: str = Header(..., alias="X-User-Id"),
):
    if session_id in _active_runs:
        raise AppException(
            code=40902,
            message="删除冲突",
            status_code=409,
            details={"thread_id": session_id, "error": "会话正在运行中，无法删除"},
        )

    graph = await _get_graph()
    snapshot = await _get_snapshot(graph, session_id)
    if not _has_values(snapshot):
        raise_session_not_found(thread_id=session_id)

    values = getattr(snapshot, "values", None) or {}
    if values.get("deleted_at"):
        raise_session_not_found(thread_id=session_id)
    _ensure_owner(values, user_id)
    await _mark_thread_deleted(graph, session_id)
    return Response(status_code=204)
