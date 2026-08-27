"""评估系统（可观测性追踪）查询接口。"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from src.core.exceptions import (
    CODE_INVALID_PARAMETER,
    CODE_SESSION_NOT_FOUND,
    raise_app_exception,
)
from src.models.common import ApiResponse
from src.models.traces import (
    LLMEventItem,
    SpanDetailItem,
    SpanSummaryItem,
    TraceDetailData,
    TraceDetailResponse,
    TraceItem,
    TraceListData,
    TraceListResponse,
    TraceMeta,
    TraceSummaryData,
    TraceSummaryResponse,
)
from src.services.tracing_db import (
    count_llm_events_by_trace,
    fetch_traces,
    get_llm_events_by_trace,
    get_spans_by_trace,
    get_trace_by_id,
)

router = APIRouter(prefix="/traces")
logger = logging.getLogger("travelmate.api.traces")

ALLOWED_TRACE_STATUSES = {"running", "success", "error", "cancelled"}


# ============================================================
# 行 -> 模型 转换辅助
# ============================================================

# 将 ISO 8601 时间文本统一为带 Z 后缀的形式。
def _normalize_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.replace("+00:00", "Z")


# 解析 ISO 时间文本为 UTC datetime，失败返回 None。
def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _to_int_ms(value: Any) -> Optional[int]:
    """把 DB 里可能为 float 的 duration_ms 规整成 int；None 原样返回。"""
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


# 根据 start/end 计算总耗时（秒，保留 1 位小数）。
def _duration_seconds(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = _parse_iso(start)
    end_dt = _parse_iso(end)
    if start_dt is None or end_dt is None:
        return None
    return round((end_dt - start_dt).total_seconds(), 1)


# 将 traces 表的行转换为列表项模型。
def _trace_item(row: Dict[str, Any]) -> TraceItem:
    start = row.get("start_time")
    end = row.get("end_time")
    return TraceItem(
        trace_id=row.get("trace_id"),
        thread_id=row.get("thread_id"),
        user_id=row.get("user_id"),
        input_message=row.get("input_message"),
        start_time=_normalize_time(start),
        end_time=_normalize_time(end),
        duration_seconds=_duration_seconds(start, end),
        status=row.get("status"),
        total_tokens=row.get("total_tokens"),
        error_message=row.get("error_message"),
        span_count=row.get("span_count"),
    )


# 将 spans 表的行转换为摘要项模型。
def _span_summary(row: Dict[str, Any]) -> SpanSummaryItem:
    return SpanSummaryItem(
        node_name=row.get("node_name"),
        duration_ms=_to_int_ms(row.get("duration_ms")),
        status=row.get("status"),
        span_type=row.get("span_type"),
    )


# 将 llm_events 表的行转换为明细项模型。
def _llm_event_item(row: Dict[str, Any]) -> LLMEventItem:
    return LLMEventItem(
        id=row.get("id"),
        model_name=row.get("model_name"),
        request_time=_normalize_time(row.get("request_time")),
        duration_ms=_to_int_ms(row.get("duration_ms")),
        prompt_text=row.get("prompt_text"),
        response_text=row.get("response_text"),
        prompt_tokens=row.get("prompt_tokens"),
        response_tokens=row.get("response_tokens"),
        total_tokens=row.get("total_tokens"),
        status=row.get("status"),
        error=row.get("error"),
    )


# 将 spans 表的行转换为详情项模型（不含 children，后续构建树时填充）。
def _span_detail_node(row: Dict[str, Any], events: list[LLMEventItem]) -> SpanDetailItem:
    return SpanDetailItem(
        span_id=row.get("span_id"),
        node_name=row.get("node_name"),
        span_type=row.get("span_type"),
        start_time=_normalize_time(row.get("start_time")),
        end_time=_normalize_time(row.get("end_time")),
        duration_ms=_to_int_ms(row.get("duration_ms")),
        status=row.get("status"),
        output_snapshot=row.get("output_snapshot"),
        parent_span_id=row.get("parent_span_id"),
        children=[],
        llm_events=events,
    )


# 根据 trace 元数据行构建 TraceMeta。
def _trace_meta(row: Dict[str, Any]) -> TraceMeta:
    return TraceMeta(
        trace_id=row.get("trace_id"),
        thread_id=row.get("thread_id"),
        user_id=row.get("user_id"),
        input_message=row.get("input_message"),
        start_time=_normalize_time(row.get("start_time")),
        end_time=_normalize_time(row.get("end_time")),
        status=row.get("status"),
        total_tokens=row.get("total_tokens"),
        error_message=row.get("error_message"),
    )


# 将扁平 spans + 分组后的 llm_events 构建为树形结构，返回根节点列表。
def _build_span_tree(
    span_rows: list[Dict[str, Any]],
    events_by_span: Dict[str, list[LLMEventItem]],
) -> list[SpanDetailItem]:
    nodes: Dict[str, SpanDetailItem] = {}
    for row in span_rows:
        span_id = row.get("span_id")
        if span_id is None:
            continue
        nodes[span_id] = _span_detail_node(row, events_by_span.get(span_id, []))

    roots: list[SpanDetailItem] = []
    for row in span_rows:
        span_id = row.get("span_id")
        node = nodes.get(span_id)
        if node is None:
            continue
        parent_id = row.get("parent_span_id")
        parent = nodes.get(parent_id) if parent_id else None
        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)
    return roots


# trace 不存在时抛出 404（复用会话不存在的业务码 40401，details 指明为追踪记录）。
def _require_trace(trace_row: Optional[Dict[str, Any]], trace_id: str) -> Dict[str, Any]:
    if not trace_row:
        raise_app_exception(
            CODE_SESSION_NOT_FOUND,
            details={"trace_id": trace_id, "error": "未找到该追踪记录"},
        )
    return trace_row


# ============================================================
# 接口
# ============================================================

# 获取 Trace 列表。
@router.get("", response_model=TraceListResponse)
async def list_traces(
    start_time: Optional[str] = Query(default=None, description="筛选开始时间（包含），ISO 8601"),
    end_time: Optional[str] = Query(default=None, description="筛选结束时间（包含），ISO 8601"),
    thread_id: Optional[str] = Query(default=None, description="会话 ID 精确匹配"),
    user_id: Optional[str] = Query(default=None, description="用户 ID 精确匹配"),
    status: Optional[str] = Query(default=None, description="追踪状态"),
    page: int = Query(default=1, ge=1, description="页码（从 1 开始）"),
    limit: int = Query(default=20, ge=1, le=100, description="每页条数（最大 100）"),
):
    if status is not None and status not in ALLOWED_TRACE_STATUSES:
        raise_app_exception(
            CODE_INVALID_PARAMETER,
            details={
                "field": "status",
                "error": "status 必须是 running / success / error / cancelled 之一",
            },
        )

    # 校验时间参数格式，非法时归到参数类型错误（40003）。
    for field, value in (("start_time", start_time), ("end_time", end_time)):
        if value is not None and _parse_iso(value) is None:
            raise_app_exception(
                CODE_INVALID_PARAMETER,
                details={"field": field, "error": f"{field} 必须是 ISO 8601 时间格式"},
            )

    rows, total = await fetch_traces(
        start_time=start_time,
        end_time=end_time,
        thread_id=thread_id,
        user_id=user_id,
        status=status,
        page=page,
        limit=limit,
    )
    total_pages = math.ceil(total / limit) if limit else 0
    data = TraceListData(
        traces=[_trace_item(row) for row in rows],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )
    return TraceListResponse(code=200, message="获取成功", data=data)


# 获取 Trace 轻量摘要。
@router.get("/{trace_id}/summary", response_model=TraceSummaryResponse)
async def get_trace_summary(trace_id: str):
    trace_row = _require_trace(await get_trace_by_id(trace_id), trace_id)
    span_rows = await get_spans_by_trace(trace_id)
    llm_call_count = await count_llm_events_by_trace(trace_id)

    total_duration_ms: Optional[int] = None
    if span_rows:
        summed = sum((row.get("duration_ms") or 0) for row in span_rows)
        total_duration_ms = int(summed) if summed else None

    # 整体状态从 spans 推断：任一 span 出错则为 error，否则为 success。
    inferred_status = "error" if any(row.get("status") == "error" for row in span_rows) else "success"

    data = TraceSummaryData(
        trace_id=trace_id,
        total_duration_ms=total_duration_ms,
        total_tokens=trace_row.get("total_tokens"),
        llm_call_count=llm_call_count,
        status=inferred_status,
        spans=[_span_summary(row) for row in span_rows],
    )
    return TraceSummaryResponse(code=200, message="获取成功", data=data)


# 获取 Trace 完整详情（含 Span 树与 LLM 调用明细）。
@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace_detail(trace_id: str):
    trace_row = _require_trace(await get_trace_by_id(trace_id), trace_id)
    span_rows = await get_spans_by_trace(trace_id)
    event_rows = await get_llm_events_by_trace(trace_id)

    events_by_span: Dict[str, list[LLMEventItem]] = defaultdict(list)
    for row in event_rows:
        span_id = row.get("span_id")
        if span_id is not None:
            events_by_span[span_id].append(_llm_event_item(row))

    span_tree = _build_span_tree(span_rows, events_by_span)
    data = TraceDetailData(
        trace=_trace_meta(trace_row),
        spans=span_tree,
    )
    return TraceDetailResponse(code=200, message="获取成功", data=data)
