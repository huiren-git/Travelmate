import type { Conversation, ConversationStatus } from '../types/chat'
import { API_BASE_URL, USER_ID } from './chat'

// 对应后端 GET /api/v1/sessions 返回的单条会话摘要（SessionItem）
export type SessionItemStatus = 'planning' | 'confirmed' | 'completed' | 'failed' | 'deleted'

export type SessionItem = {
  thread_id: string
  destination: string
  start_date: string
  duration: number
  status: SessionItemStatus
  last_updated: string
}

type SessionListData = {
  sessions: SessionItem[]
  next_cursor: string | null
  has_more: boolean
}

type SessionListResponse = {
  code: number
  message: string
  data: SessionListData
}

export type FetchSessionsParams = {
  limit?: number
  cursor?: string | null
  signal?: AbortSignal
}

export type FetchSessionsResult = {
  sessions: SessionItem[]
  nextCursor: string | null
  hasMore: boolean
}

async function readErrorMessage(response: Response, fallback: string) {
  const text = await response.text()
  if (!text) {
    return response.statusText || fallback
  }

  try {
    const payload = JSON.parse(text) as {
      message?: unknown
      details?: { error?: unknown }
    }

    if (typeof payload.message === 'string' && payload.message.trim()) {
      return payload.message
    }

    if (payload.details && typeof payload.details.error === 'string' && payload.details.error.trim()) {
      return payload.details.error
    }
  } catch {
    // 继续返回原始文本。
  }

  return text
}

export async function fetchSessions(params: FetchSessionsParams = {}): Promise<FetchSessionsResult> {
  const search = new URLSearchParams()
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.cursor) search.set('cursor', params.cursor)

  const query = search.toString()
  const url = `${API_BASE_URL}/sessions${query ? `?${query}` : ''}`

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'X-User-Id': USER_ID,
    },
    signal: params.signal,
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, '获取会话列表失败'))
  }

  const payload = (await response.json()) as SessionListResponse
  const data = payload.data ?? { sessions: [], next_cursor: null, has_more: false }

  return {
    sessions: data.sessions ?? [],
    nextCursor: data.next_cursor ?? null,
    hasMore: Boolean(data.has_more),
  }
}

/**
 * 拉取当前用户的全部会话，自动翻页到末尾。
 */
export async function fetchAllSessions(signal?: AbortSignal): Promise<SessionItem[]> {
  const sessions: SessionItem[] = []
  let cursor: string | null = null

  while (true) {
    const result = await fetchSessions({ limit: 50, cursor, signal })
    sessions.push(...result.sessions)

    if (!result.hasMore || !result.nextCursor) {
      break
    }

    cursor = result.nextCursor
  }

  return sessions
}

/**
 * DELETE /api/v1/sessions/{session_id}
 * 逻辑删除单个会话。
 */
export async function deleteSession(threadId: string, signal?: AbortSignal): Promise<void> {
  const url = `${API_BASE_URL}/sessions/${encodeURIComponent(threadId)}`

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'X-User-Id': USER_ID,
    },
    signal,
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, '删除会话失败'))
  }
}

function toConversationStatus(status: SessionItemStatus): ConversationStatus {
  // planning/confirmed 视为「进行中」；completed 视为「已完成」；
  // deleted 为软删除项（后端通常不返回），此处兜底再过滤一次。
  return status === 'completed' || status === 'failed' ? '已完成' : '进行中'
}

function toRelativeUpdatedAt(iso: string): string {
  const updated = new Date(iso)
  if (Number.isNaN(updated.getTime())) {
    return iso
  }

  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfUpdated = new Date(updated.getFullYear(), updated.getMonth(), updated.getDate())
  const diffDays = Math.round((startOfToday.getTime() - startOfUpdated.getTime()) / (24 * 60 * 60 * 1000))

  if (diffDays <= 0) return '今天'
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 14) return '上周'
  const weeks = Math.floor(diffDays / 7)
  if (diffDays < 30) return `${weeks}周前`
  return `${updated.getMonth() + 1}月${updated.getDate()}日`
}

export function mapSessionItemToConversation(item: SessionItem): Conversation {
  return {
    id: item.thread_id,
    title: `${item.destination}${item.duration}日游`,
    updatedAt: toRelativeUpdatedAt(item.last_updated),
    status: toConversationStatus(item.status),
  }
}

export function mapSessionItemsToConversations(items: SessionItem[]): Conversation[] {
  return items.filter((item) => item.status !== 'deleted').map(mapSessionItemToConversation)
}

// ============================================================
// 会话快照 GET /sessions/{id}/snapshot
// ============================================================

// 对应后端 TravelAgentState 中 ItineraryItem（snake_case，与后端 JSON 一致）
export type SnapshotItineraryItem = {
  time: string
  activity: string
  duration: string
  address?: string | null
  image_url: string
  status: 'completed' | 'ongoing' | 'upcoming'
  tips?: string | null
}

export type SnapshotDayPlan = {
  day: number
  date: string
  items: SnapshotItineraryItem[]
}

export type SnapshotBudgetDetail = {
  level: 'economy' | 'mid' | 'luxury'
  total: number
  // { transport, hotel, food, tickets }
  detail: Record<string, number>
  saving_tips?: string[] | null
}

// snapshot 响应里 state.blackboard 即完整 TravelAgentState 的 JSON。
// 这里只声明前端会用到的字段，其余按需取值。
export type SessionSnapshotBlackboard = {
  messages?: Array<{ type: string; content: unknown }>
  destination?: string | null
  start_date?: string | null
  duration?: number | null
  daily_itinerary?: SnapshotDayPlan[] | null
  draft_daily_itinerary?: SnapshotDayPlan[] | null
  budget?: SnapshotBudgetDetail | null
  draft_budget?: SnapshotBudgetDetail | null
  structured_preferences?: Record<string, unknown> | null
  is_finished?: boolean
  terminal_status?: 'running' | 'confirmed' | 'failed'
  failure_reason?: string | null
  summary_text?: string | null
} & Record<string, unknown>

export type SessionSnapshotData = {
  session_id: string
  state: {
    task_list: unknown[]
    blackboard: SessionSnapshotBlackboard
  }
  graph_structure: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
}

type SnapshotResponse = {
  code: number
  message: string
  data: SessionSnapshotData
}

export async function fetchSessionSnapshot(
  threadId: string,
  signal?: AbortSignal,
): Promise<SessionSnapshotData> {
  const url = `${API_BASE_URL}/sessions/${encodeURIComponent(threadId)}/snapshot`

  const response = await fetch(url, {
    method: 'GET',
    headers: { 'X-User-Id': USER_ID },
    signal,
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, '获取会话快照失败'))
  }

  const payload = (await response.json()) as SnapshotResponse
  return payload.data
}
