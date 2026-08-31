import type { StructuredPreferences } from '../types/chat'

export type ParsedSseEvent = {
  event: string
  data: unknown
}

export type ChatStreamRequest = {
  thread_id: string
  message: string
  current_time?: string
  structured_input?: StructuredPreferences
}

export type UserDecision = {
  action: 'accept' | 'modify' | 'reject'
  hint?: string
  note?: string
}

export type ResumeChatRequest = {
  thread_id: string
  user_decision: UserDecision
}

export async function confirmLogistics(threadId: string, itemKey: string) {
  const response = await fetch(`${API_BASE_URL}/chat/logistics/confirm`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-User-Id': USER_ID },
    body: JSON.stringify({ thread_id: threadId, item_key: itemKey }),
  })
  if (!response.ok) throw new Error((await response.text()) || response.statusText)
  const payload = await response.json() as { data?: unknown }
  return payload.data
}

// 后端 BudgetOverrunHandler.build_payload 产出的中断 payload（挂在前端 done 事件的 tasks[].interrupts[].value）。
export type BudgetInterruptPayload = {
  type: string
  title?: string
  description?: string
  options?: Array<{ id: string; label: string; default?: boolean; ui_hint?: string }>
  extra?: Record<string, unknown>
}

type ParseSseResult = {
  events: ParsedSseEvent[]
  rest: string
}

export const API_BASE_URL = '/api/v1'
const USER_ID_STORAGE_KEY = 'travelmate-user-id'
export let USER_ID = typeof localStorage === 'undefined' ? '1' : localStorage.getItem(USER_ID_STORAGE_KEY) || '1'

export function setUserId(userId: string) {
  USER_ID = userId
  if (typeof localStorage !== 'undefined') localStorage.setItem(USER_ID_STORAGE_KEY, userId)
}

export function createChatThreadId() {
  const bytes = new Uint8Array(8)
  crypto.getRandomValues(bytes)

  const shortCode = Array.from(bytes, byte =>
    byte.toString(16).padStart(2, '0')
  ).join('')

  return `thr_${shortCode}`
}

function parseSseMessages(text: string): ParseSseResult {
  const events: ParsedSseEvent[] = []
  const completeBoundary = text.lastIndexOf('\n\n')

  if (completeBoundary === -1) {
    return { events, rest: text }
  }

  const completeText = text.slice(0, completeBoundary)
  const rest = text.slice(completeBoundary + 2)

  for (const block of completeText.split('\n\n')) {
    if (!block.trim()) {
      continue
    }

    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice('event:'.length).trim()
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trimStart())
      }
    }

    if (dataLines.length === 0) {
      continue
    }

    events.push({ event, data: JSON.parse(dataLines.join('\n')) })
  }

  return { events, rest }
}

export async function streamChat(
  request: ChatStreamRequest,
  onEvent: (event: ParsedSseEvent) => void | Promise<void>,
  signal?: AbortSignal,
) {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': USER_ID,
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText || 'Chat request failed')
  }
  if (!response.body) {
    throw new Error('Streaming response has no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSseMessages(buffer)
      buffer = parsed.rest
      for (const event of parsed.events) {
        await onEvent(event)
      }
    }

    buffer += decoder.decode()
    const parsed = parseSseMessages(buffer)
    for (const event of parsed.events) {
      await onEvent(event)
    }
  } finally {
    reader.releaseLock()
  }
}

export async function stopChat(threadId: string) {
  const response = await fetch(`${API_BASE_URL}/chat/stop/${encodeURIComponent(threadId)}`, {
    method: 'POST',
    headers: { 'X-User-Id': USER_ID },
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText || 'Stop request failed')
  }
  return response.json() as Promise<{ code: number; data?: unknown }>
}

// 恢复处于 LangGraph interrupt 状态的会话并返回后续 SSE 流（人机协同：用户确认超支等）。
export async function resumeChat(
  request: ResumeChatRequest,
  onEvent: (event: ParsedSseEvent) => void | Promise<void>,
) {
  const response = await fetch(`${API_BASE_URL}/chat/resume`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Id': USER_ID,
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText || 'Resume request failed')
  }
  if (!response.body) {
    throw new Error('Streaming response has no body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSseMessages(buffer)
      buffer = parsed.rest
      for (const event of parsed.events) {
        await onEvent(event)
      }
    }

    buffer += decoder.decode()
    const parsed = parseSseMessages(buffer)
    for (const event of parsed.events) {
      await onEvent(event)
    }
  } finally {
    reader.releaseLock()
  }
}
