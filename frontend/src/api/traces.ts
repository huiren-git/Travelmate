import type {
  ErrorResponse,
  TraceDetailData,
  TraceFilters,
  TraceListData,
  TraceSummaryData,
} from '../types/trace'
import { useAppSettingsStore } from '../store/useAppSettingsStore'

const API_BASE_URL = '/api/v1'
const USER_ID = 'demo-user'

/** 节点展示名映射（用于友好展示，未知节点回退到原 node_name） */
export const NODE_LABELS: Record<string, { zh: string; en: string }> = {
  pre_fetcher: { zh: '预取', en: 'Prefetch' },
  supervisor: { zh: '调度', en: 'Schedule' },
  itinerary_agent: { zh: '行程', en: 'Itinerary' },
  validator: { zh: '校验', en: 'Validate' },
  budget_agent: { zh: '预算', en: 'Budget' },
  summarizer: { zh: '总结', en: 'Summarize' },
}

export function getNodeLabel(nodeName: string): string {
  const lang = useAppSettingsStore.getState().language === '英文' ? 'en' : 'zh'
  // 1) 精确匹配（如 "utils.llm_utils.call_llm"）
  if (NODE_LABELS[nodeName]) return NODE_LABELS[nodeName][lang]
  // 2) 退而取模块段：agents.itinerary_agent.xxx -> itinerary_agent
  const seg = nodeName.split('.')[1]
  if (seg && NODE_LABELS[seg]) return NODE_LABELS[seg][lang]
  return nodeName
}

/** 跨度类型标签 */
export const SPAN_TYPE_LABELS: Record<string, { zh: string; en: string }> = {
  llm: { zh: 'LLM', en: 'LLM' },
  io: { zh: 'IO', en: 'IO' },
  function: { zh: '函数', en: 'Function' },
  workflow: { zh: '工作流', en: 'Workflow' },
}

export function getSpanTypeLabel(spanType: string): string {
  const lang = useAppSettingsStore.getState().language === '英文' ? 'en' : 'zh'
  return SPAN_TYPE_LABELS[spanType]?.[lang] ?? spanType
}

/**
 * 统一解析接口响应：
 * - HTTP 非 2xx：抛出含业务 message 的 Error
 * - 业务 code 非 200：抛出含 message 的 Error
 * - 成功：返回 data
 */
async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = response.statusText || `请求失败（HTTP ${response.status}）`
    let parsed: unknown
    try {
      parsed = await response.json()
    } catch {
      const text = await response.text().catch(() => '')
      if (text) message = text
      throw new Error(message)
    }
    const err = parsed as ErrorResponse | undefined
    if (err?.message) message = err.message
    throw new Error(message)
  }

  const payload = (await response.json()) as { code: number; data?: T; message?: string }
  if (payload.code !== 200 || !payload.data) {
    throw new Error(payload.message ?? `请求失败（code ${payload.code}）`)
  }
  return payload.data
}

function buildTraceListParams(filters: TraceFilters): Record<string, string> {
  const params: Record<string, string> = {}
  if (filters.start_time) params.start_time = filters.start_time
  if (filters.end_time) params.end_time = filters.end_time
  if (filters.thread_id) params.thread_id = filters.thread_id.trim()
  if (filters.user_id) params.user_id = filters.user_id.trim()
  if (filters.status && filters.status !== 'all') params.status = filters.status
  if (filters.page) params.page = String(filters.page)
  if (filters.limit) params.limit = String(filters.limit)
  return params
}

/** GET /api/v1/traces —— 获取 Trace 列表 */
export async function fetchTraces(filters: TraceFilters = {}): Promise<TraceListData> {
  const params = buildTraceListParams(filters)
  const search = new URLSearchParams(params).toString()
  const url = `${API_BASE_URL}/traces${search ? `?${search}` : ''}`

  const response = await fetch(url, {
    method: 'GET',
    headers: { 'X-User-Id': USER_ID },
  })
  return parseResponse<TraceListData>(response)
}

/** GET /api/v1/traces/{trace_id}/summary —— 获取 Trace 轻量摘要 */
export async function fetchTraceSummary(traceId: string): Promise<TraceSummaryData> {
  const response = await fetch(`${API_BASE_URL}/traces/${encodeURIComponent(traceId)}/summary`, {
    method: 'GET',
    headers: { 'X-User-Id': USER_ID },
  })
  return parseResponse<TraceSummaryData>(response)
}

/** GET /api/v1/traces/{trace_id} —— 获取 Trace 完整详情 */
export async function fetchTraceDetail(traceId: string): Promise<TraceDetailData> {
  const response = await fetch(`${API_BASE_URL}/traces/${encodeURIComponent(traceId)}`, {
    method: 'GET',
    headers: { 'X-User-Id': USER_ID },
  })
  return parseResponse<TraceDetailData>(response)
}

export const TRACE_API_BASE_URL = API_BASE_URL
