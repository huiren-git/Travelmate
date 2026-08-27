import type { LlmEventItem, SpanDetailItem, TraceMeta } from '../types/trace'

/** 扁平化 Span 树（深度优先，保留父子顺序） */
export function flattenSpans(spans: SpanDetailItem[]): SpanDetailItem[] {
  const result: SpanDetailItem[] = []
  const walk = (list: SpanDetailItem[]) => {
    for (const span of list) {
      result.push(span)
      if (span.children?.length) walk(span.children)
    }
  }
  walk(spans)
  return result
}

/** LLM 事件 + 来源 Span 信息 */
export type LlmEventWithSpan = LlmEventItem & {
  span_id: string
  span_node_name: string
}

/** 收集所有 Span 下的 LLM 事件，并标注来源 Span */
export function collectLlmEvents(spans: SpanDetailItem[]): LlmEventWithSpan[] {
  const flat = flattenSpans(spans)
  // span_id -> span 映射，用于向上解析真正的调用方（call_llm 叶子节点的父 span）
  const byId = new Map(flat.map((s) => [s.span_id, s]))
  const events: LlmEventWithSpan[] = []
  for (const span of flat) {
    if (!span.llm_events?.length) continue
    // 当前 span 是 call_llm 叶子节点，真正的调用方是它的父 span
    const caller = span.parent_span_id ? byId.get(span.parent_span_id) : undefined
    const sourceName = caller?.node_name ?? span.node_name
    for (const event of span.llm_events) {
      events.push({ ...event, span_id: span.span_id, span_node_name: sourceName })
    }
  }
  return events
}

/** 计算相对 trace 起始的偏移（毫秒） */
export function getSpanStartOffsetMs(traceStartIso: string, spanStartIso: string): number {
  const start = new Date(traceStartIso).getTime()
  const spanStart = new Date(spanStartIso).getTime()
  if (Number.isNaN(start) || Number.isNaN(spanStart)) return 0
  return Math.max(0, spanStart - start)
}

/** 计算 Trace 总耗时（毫秒）：优先 end_time - start_time，否则用 spans 里的最大 end_time */
export function computeTraceDurationMs(trace: TraceMeta, spans: SpanDetailItem[]): number {
  const startMs = new Date(trace.start_time).getTime()
  if (!Number.isNaN(startMs) && trace.end_time) {
    const endMs = new Date(trace.end_time).getTime()
    if (!Number.isNaN(endMs)) return Math.max(0, endMs - startMs)
  }
  const flat = flattenSpans(spans)
  let maxEnd = startMs
  for (const span of flat) {
    if (!span.end_time) continue
    const ms = new Date(span.end_time).getTime()
    if (!Number.isNaN(ms) && ms > maxEnd) maxEnd = ms
  }
  return Number.isNaN(maxEnd) || Number.isNaN(startMs) ? 0 : Math.max(0, maxEnd - startMs)
}
