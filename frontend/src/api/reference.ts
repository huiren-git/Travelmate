import { API_BASE_URL, USER_ID, type ParsedSseEvent } from './chat'

export type ReferenceTrip = {
  id: number
  destination: string
  duration: number
  score: number
  tags: string[]
  experience_tips: string
  usage_count: number
  travelers?: number
}

async function responseError(response: Response, fallback: string) {
  const text = await response.text()
  try {
    const payload = JSON.parse(text) as { message?: unknown; detail?: unknown }
    if (typeof payload.message === 'string' && payload.message) return payload.message
    if (typeof payload.detail === 'string' && payload.detail) return payload.detail
  } catch {
    // Non-JSON error responses still use their text below.
  }
  return text || response.statusText || fallback
}

export async function fetchReferenceTrips() {
  const response = await fetch(`${API_BASE_URL}/reference/list`)
  if (!response.ok) throw new Error(await responseError(response, '加载参考行程失败'))
  return (await response.json()).data as { items: ReferenceTrip[] }
}

export async function adoptReference(id: number, body: Record<string, unknown>, onEvent: (event: ParsedSseEvent) => void) {
  const response = await fetch(`${API_BASE_URL}/reference/${id}/adopt/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Id': USER_ID },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await responseError(response, '采纳失败'))
  if (!response.body) throw new Error('采纳失败：服务未返回数据流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const part of parts) {
        const event = part.match(/event: (.*)/)?.[1] || 'message'
        const raw = part.match(/data: (.*)/)?.[1]
        if (raw) onEvent({ event, data: JSON.parse(raw) })
      }
    }
  } finally {
    reader.releaseLock()
  }
}
