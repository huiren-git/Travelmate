import { API_BASE_URL, USER_ID } from './chat'

// 对应后端 PreferenceCategory（src/models/preferences.py）
export type PreferenceCategory =
  | 'diet'
  | 'pace'
  | 'budget'
  | 'interest'
  | 'accommodation'
  | 'transport'

export type PreferenceSource = 'inferred' | 'manual'

export type PreferenceItem = {
  id: string
  category: PreferenceCategory
  content: string
  source: PreferenceSource
  confidence: number
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
  deleted_at?: string | null
}

export type PreferenceSummary = {
  total: number
  active_count: number
  categories: Record<string, number>
}

export type PreferenceListData = {
  preferences: PreferenceItem[]
  summary: PreferenceSummary
}

type PreferenceListResponse = {
  code: number
  message: string
  data: PreferenceListData
}

export type PreferenceItemInput = {
  category: PreferenceCategory
  content: string
}

const EMPTY_DATA: PreferenceListData = {
  preferences: [],
  summary: { total: 0, active_count: 0, categories: {} },
}

/**
 * GET /api/v1/users/me/preferences
 * 拉取当前用户的全部偏好（含推断）。前端按 source=manual 重建表单。
 */
export async function fetchPreferences(signal?: AbortSignal): Promise<PreferenceListData> {
  const url = `${API_BASE_URL}/users/me/preferences?include_inferred=true`
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'X-User-Id': USER_ID },
    signal,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText || '获取偏好失败')
  }

  const payload = (await response.json()) as PreferenceListResponse
  return payload.data ?? EMPTY_DATA
}

/**
 * PUT /api/v1/users/me/preferences
 * 整体替换当前用户的手动偏好（推断偏好保留不动）。
 */
export async function replacePreferences(
  items: PreferenceItemInput[],
  signal?: AbortSignal,
): Promise<PreferenceListData> {
  const url = `${API_BASE_URL}/users/me/preferences`
  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'X-User-Id': USER_ID,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ items }),
    signal,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || response.statusText || '保存偏好失败')
  }

  const payload = (await response.json()) as PreferenceListResponse
  return payload.data ?? EMPTY_DATA
}
