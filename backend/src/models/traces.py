"""评估系统（可观测性追踪）数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.models.common import ApiResponse

# ============================================================
# 枚举类型别名（与 API 说明书一致）
# ============================================================

TraceStatus = Literal["running", "success", "error", "cancelled"]
SpanType = Literal["llm", "io", "function", "workflow"]
SpanStatus = Literal["running", "success", "error"]
LLMEventStatus = Literal["success", "error", "timeout"]
SummaryStatus = Literal["success", "error"]


# ============================================================
# Trace 列表
# ============================================================

class TraceItem(BaseModel):
    """追踪列表中的单条记录，聚合了 Span 数量与总耗时。"""

    trace_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    input_message: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: float | None = None
    status: TraceStatus | None = None
    total_tokens: int | None = None
    error_message: str | None = None
    span_count: int | None = None


class TraceListData(BaseModel):
    """追踪列表分页数据。"""

    traces: list[TraceItem] | None = None
    total: int | None = None
    page: int | None = None
    limit: int | None = None
    total_pages: int | None = None


class TraceListResponse(ApiResponse[TraceListData]):
    """追踪列表统一响应。"""


# ============================================================
# Trace 摘要
# ============================================================

class SpanSummaryItem(BaseModel):
    """Span 轻量摘要，用于列表页快速预览。"""

    node_name: str | None = None
    duration_ms: int | None = None
    status: SpanStatus | None = None
    span_type: SpanType | None = None


class TraceSummaryData(BaseModel):
    """Trace 概览指标及节点耗时列表。"""

    trace_id: str | None = None
    total_duration_ms: int | None = None
    total_tokens: int | None = None
    llm_call_count: int | None = None
    status: SummaryStatus | None = None
    spans: list[SpanSummaryItem] | None = None


class TraceSummaryResponse(ApiResponse[TraceSummaryData]):
    """Trace 摘要统一响应。"""


# ============================================================
# Trace 详情
# ============================================================

class LLMEventItem(BaseModel):
    """单次 LLM 调用明细（Prompt/Response）。"""

    id: int | None = None
    model_name: str | None = None
    request_time: str | None = None
    duration_ms: int | None = None
    prompt_text: str | None = None
    response_text: str | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    status: LLMEventStatus | None = None
    error: str | None = None


class SpanDetailItem(BaseModel):
    """Span 详情，含子 Span 树与挂载的 LLM 调用明细。"""

    span_id: str | None = None
    node_name: str | None = None
    span_type: SpanType | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: int | None = None
    status: SpanStatus | None = None
    output_snapshot: str | None = None
    parent_span_id: str | None = None
    children: list[SpanDetailItem] | None = None
    llm_events: list[LLMEventItem] | None = None


# 递归引用需要在类定义完成后重建。
SpanDetailItem.model_rebuild()


class TraceMeta(BaseModel):
    """Trace 元数据（不含 Span 数量与耗时）。"""

    trace_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    input_message: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    status: TraceStatus | None = None
    total_tokens: int | None = None
    error_message: str | None = None


class TraceDetailData(BaseModel):
    """Trace 完整详情，包含 Span 树形结构。"""

    trace: TraceMeta | None = None
    spans: list[SpanDetailItem] | None = None


class TraceDetailResponse(ApiResponse[TraceDetailData]):
    """Trace 详情统一响应。"""
