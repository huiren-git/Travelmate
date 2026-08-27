/**
 * 评估系统可观测性接口类型定义
 * 对应接口文档：GET /api/v1/traces、/traces/{trace_id}/summary、/traces/{trace_id}
 */

// ===== 状态枚举 =====

/** Trace 整体状态（TraceItem / TraceMeta） */
export type TraceStatus = 'running' | 'success' | 'error' | 'cancelled'

/** Span 执行状态（SpanSummaryItem / SpanDetailItem） */
export type SpanStatus = 'running' | 'success' | 'error'

/** LLM 调用状态（LlmEventItem） */
export type LlmCallStatus = 'success' | 'error' | 'timeout'

/** 跨度类型 */
export type SpanType = 'llm' | 'io' | 'function' | 'workflow'

// ===== 列表接口 GET /api/v1/traces =====

/** Trace 列表项（轻量） */
export type TraceListItem = {
  trace_id: string
  thread_id: string
  user_id: string
  /** 用户首条输入消息（截断） */
  input_message: string | null
  /** ISO 8601 开始时间 */
  start_time: string
  /** 结束时间，可为空（表示进行中） */
  end_time: string | null
  /** 总耗时（秒） */
  duration_seconds: number | null
  status: TraceStatus
  total_tokens: number
  /** 错误信息（如有） */
  error_message: string | null
  /** 关联的 Span 数量 */
  span_count: number
}

export type TraceListData = {
  traces: TraceListItem[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export type TraceListResponse = {
  code: number
  data: TraceListData
}

// ===== 摘要接口 GET /api/v1/traces/{trace_id}/summary =====

/** 摘要中的 Span 节点（轻量） */
export type SpanSummaryItem = {
  node_name: string
  duration_ms: number | null
  status: SpanStatus
  span_type: SpanType
}

export type TraceSummaryData = {
  trace_id: string
  total_duration_ms: number | null
  total_tokens: number
  llm_call_count: number
  status: TraceStatus
  spans: SpanSummaryItem[]
}

export type TraceSummaryResponse = {
  code: number
  data: TraceSummaryData
}

// ===== 详情接口 GET /api/v1/traces/{trace_id} =====

/** LLM 调用明细 */
export type LlmEventItem = {
  id: number
  model_name: string
  request_time: string
  duration_ms: number
  /** 完整 Prompt（System + User） */
  prompt_text: string
  response_text: string
  prompt_tokens: number
  response_tokens: number
  total_tokens: number
  status: LlmCallStatus
  error: string | null
}

/** 详情中的 Span 节点（树形） */
export type SpanDetailItem = {
  span_id: string
  node_name: string
  span_type: SpanType
  start_time: string
  end_time: string | null
  duration_ms: number | null
  status: SpanStatus
  /** 输出摘要（截断） */
  output_snapshot: string | null
  parent_span_id: string | null
  children: SpanDetailItem[]
  llm_events: LlmEventItem[]
}

/** Trace 元信息 */
export type TraceMeta = {
  trace_id: string
  thread_id: string
  user_id: string
  input_message: string | null
  start_time: string
  end_time: string | null
  status: TraceStatus
  total_tokens: number
  error_message: string | null
}

export type TraceDetailData = {
  trace: TraceMeta
  spans: SpanDetailItem[]
}

export type TraceDetailResponse = {
  code: number
  data: TraceDetailData
}

// ===== 错误响应 =====

export type ErrorDetail = {
  field?: string
  error?: string
  [key: string]: unknown
}

export type ErrorResponse = {
  code: number
  message: string
  details?: ErrorDetail | ErrorDetail[]
}

// ===== 前端筛选器 =====

export type TraceFilters = {
  start_time?: string
  end_time?: string
  thread_id?: string
  user_id?: string
  status?: TraceStatus | 'all'
  page?: number
  limit?: number
}
