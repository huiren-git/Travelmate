# Real API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace frontend mock data with real backend requests and add the missing user profile API plus documentation.

**Architecture:** Add one backend `users` router and a small user service, then build a frontend API layer that centralizes request headers, error handling, response typing, SSE parsing, and mapper functions. Existing React hooks keep owning page state, but their data sources change from static stores to API calls and mapper outputs.

**Tech Stack:** FastAPI, Pydantic, pytest, React 19, TypeScript, Vite, Ant Design, Vitest.

---

## Scope Check

The work crosses backend, frontend, and API documentation, but each piece supports one end-to-end outcome: real API-backed Travelmate screens. Keep it as one plan because every task is needed to remove the mock data safely.

## File Structure

- Create `backend/src/models/users.py`: Pydantic response models for user profile data.
- Create `backend/src/services/user_service.py`: deterministic development user profile source keyed by `X-User-Id`.
- Create `backend/src/api/v1/users.py`: FastAPI route for `GET /api/v1/users/me/profile`.
- Modify `backend/src/main.py`: register the users router.
- Create `backend/tests/test_users_api.py`: user profile route tests.
- Create `api说明书/用户信息.md`: API docs for user profile.
- Modify `frontend/package.json`: add `test` script and Vitest dev dependency.
- Create `frontend/src/api/types.ts`: backend wire types used by the frontend.
- Create `frontend/src/api/client.ts`: base API client with `X-User-Id` and error normalization.
- Create `frontend/src/api/users.ts`: profile API wrapper.
- Create `frontend/src/api/preferences.ts`: preference API wrappers.
- Create `frontend/src/api/sessions.ts`: session list, snapshot, and delete wrappers.
- Create `frontend/src/api/chat.ts`: chat stream wrapper and SSE parsing.
- Create `frontend/src/api/mappers.ts`: backend-to-UI mapping functions.
- Create `frontend/src/api/__tests__/client.test.ts`: API client tests.
- Create `frontend/src/api/__tests__/mappers.test.ts`: mapping tests.
- Create `frontend/src/api/__tests__/chat.test.ts`: SSE parser tests.
- Modify `frontend/src/hooks/useProfilePageData.ts`: load profile, preferences, and stats from APIs.
- Modify `frontend/src/hooks/useHistoryPageData.ts`: load sessions and selected snapshot from APIs.
- Modify `frontend/src/hooks/useChatPageState.ts`: load sessions and send real `chat/stream` requests.
- Modify `frontend/src/components/common/AppHeader.tsx`: remove profile mock import and load profile via API.
- Modify `frontend/src/layouts/HistoryLayout.tsx`: accept empty or loading history state.
- Modify `frontend/src/components/history/HistoryDetailPanel.tsx`: render empty state when no history is selected.
- Modify `frontend/src/components/profile/TravelHistoryOutlet.tsx`: receive histories through outlet context instead of importing mock data.
- Modify `frontend/src/components/profile/ProfileOutletPanel.tsx`: pass real histories into profile history outlet.
- Modify `frontend/src/types/profile.ts`, `frontend/src/types/history.ts`, and `frontend/src/types/chat.ts`: add API-backed loading/error fields only where hooks expose them.
- Delete or stop importing `frontend/src/assets/profile/profileData.ts`, `frontend/src/store/historyData.ts`, and `frontend/src/store/chatStore.ts` after all consumers are migrated.

---

### Task 1: Backend User Profile API

**Files:**
- Create: `backend/src/models/users.py`
- Create: `backend/src/services/user_service.py`
- Create: `backend/src/api/v1/users.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/test_users_api.py`

- [ ] **Step 1: Write the failing user profile API tests**

Create `backend/tests/test_users_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1 import users as users_api
from src.core.exceptions import setup_exception_handlers


def _client() -> TestClient:
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(users_api.router, prefix="/api/v1")
    return TestClient(app)


def test_get_user_profile_returns_current_user_profile():
    client = _client()

    response = client.get("/api/v1/users/me/profile", headers={"X-User-Id": "user-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["message"] == "获取成功"
    assert body["data"] == {
        "avatar_url": "",
        "nickname": "Travelmate User user-1",
        "username": "user-1",
        "email": "user-1@travelmate.local",
        "current_city": "",
    }


def test_get_user_profile_requires_user_id_header():
    client = _client()

    response = client.get("/api/v1/users/me/profile")

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 40101
    assert body["details"] == {"header": "X-User-Id"}
```

- [ ] **Step 2: Run the backend profile test and verify red**

Run:

```bash
cd backend
python -m pytest tests/test_users_api.py -q
```

Expected: FAIL because `src.api.v1.users` does not exist.

- [ ] **Step 3: Add backend profile models**

Create `backend/src/models/users.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from src.models.common import ApiResponse


class UserProfileData(BaseModel):
    avatar_url: str
    nickname: str
    username: str
    email: str
    current_city: str


class UserProfileResponse(ApiResponse[UserProfileData]):
    pass
```

- [ ] **Step 4: Add the user profile service**

Create `backend/src/services/user_service.py`:

```python
from __future__ import annotations

import re

from src.models.users import UserProfileData


class UserService:
    async def get_profile(self, user_id: str) -> UserProfileData:
        username = self._username_from_user_id(user_id)
        return UserProfileData(
            avatar_url="",
            nickname=f"Travelmate User {user_id}",
            username=username,
            email=f"{username}@travelmate.local",
            current_city="",
        )

    @staticmethod
    def _username_from_user_id(user_id: str) -> str:
        username = re.sub(r"[^a-zA-Z0-9_.-]+", "-", user_id.strip()).strip("-").lower()
        return username or "travelmate-user"


user_service = UserService()
```

- [ ] **Step 5: Add the users router**

Create `backend/src/api/v1/users.py`:

```python
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header

from src.core.exceptions import raise_missing_user_id
from src.models.common import ApiResponse
from src.models.users import UserProfileData
from src.services.user_service import user_service

router = APIRouter(prefix="/users/me")


@router.get("/profile", response_model=ApiResponse[UserProfileData])
async def get_user_profile(
    user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
):
    if not user_id or not user_id.strip():
        raise_missing_user_id(details={"header": "X-User-Id"})

    profile = await user_service.get_profile(user_id.strip())
    return ApiResponse(code=200, message="获取成功", data=profile)
```

- [ ] **Step 6: Register the users router**

Modify the import and router registration block at the bottom of `backend/src/main.py`:

```python
from src.api.v1 import chat
from src.api.v1 import health
from src.api.v1 import preferences
from src.api.v1 import sessions
from src.api.v1 import users

app.include_router(health.router, prefix="/api/v1", tags=["系统运维"])
app.include_router(chat.router, prefix="/api/v1", tags=["AI 对话和行程生成"])
app.include_router(preferences.router, prefix="/api/v1", tags=["用户画像"])
app.include_router(sessions.router, prefix="/api/v1", tags=["行程管理"])
app.include_router(users.router, prefix="/api/v1", tags=["用户信息"])
```

- [ ] **Step 7: Run the backend profile test and verify green**

Run:

```bash
cd backend
python -m pytest tests/test_users_api.py -q
```

Expected: PASS with `2 passed`.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add backend/src/models/users.py backend/src/services/user_service.py backend/src/api/v1/users.py backend/src/main.py backend/tests/test_users_api.py
git commit -m "feat: add user profile API"
```

---

### Task 2: User Profile API Documentation

**Files:**
- Create: `api说明书/用户信息.md`

- [ ] **Step 1: Write the API documentation**

Create `api说明书/用户信息.md`:

````markdown
# 用户信息

当前文档描述 Travelmate 前端获取当前用户基础资料的接口。开发阶段使用 `X-User-Id` 请求头识别用户，后续可升级为 Token 鉴权。

## GET 获取当前用户资料

`GET /api/v1/users/me/profile`

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| X-User-Id | header | string | 是 | 当前用户唯一标识 |

### 200 Response

```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "avatar_url": "",
    "nickname": "Travelmate User user-1",
    "username": "user-1",
    "email": "user-1@travelmate.local",
    "current_city": ""
  }
}
```

### 401 Response

```json
{
  "code": 40101,
  "message": "缺少用户身份标识",
  "details": {
    "header": "X-User-Id"
  }
}
```

### 403 Response

```json
{
  "code": 40301,
  "message": "无权操作该资源"
}
```

## 数据模型

### UserProfileData

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| avatar_url | string | 是 | 用户头像 URL；为空时前端显示默认头像 |
| nickname | string | 是 | 用户昵称 |
| username | string | 是 | 用户名 |
| email | string | 是 | 用户邮箱 |
| current_city | string | 是 | 当前城市；为空时前端显示未设置 |

### GetUserProfileResponse

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | integer | 是 | 业务状态码 |
| message | string | 是 | 响应消息 |
| data | UserProfileData | 是 | 用户资料 |

### ErrorResponse

| 名称 | 类型 | 必填 | 说明 |
|---|---|---|---|
| code | integer | 是 | 业务错误码 |
| message | string | 是 | 用户可读错误信息 |
| details | object | 否 | 错误详情 |
````

- [ ] **Step 2: Verify the docs file exists**

Run:

```bash
Test-Path 'api说明书\用户信息.md'
```

Expected: `True`.

- [ ] **Step 3: Commit Task 2**

Run:

```bash
git add "api说明书/用户信息.md"
git commit -m "docs: add user profile API docs"
```

---

### Task 3: Frontend API Test Harness and API Layer

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/users.ts`
- Create: `frontend/src/api/preferences.ts`
- Create: `frontend/src/api/sessions.ts`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/mappers.ts`
- Create: `frontend/src/api/__tests__/client.test.ts`
- Create: `frontend/src/api/__tests__/mappers.test.ts`
- Create: `frontend/src/api/__tests__/chat.test.ts`

- [ ] **Step 1: Add Vitest to package metadata**

Modify `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "devDependencies": {
    "vitest": "^4.3.0"
  }
}
```

Keep all existing dependencies and dev dependencies; only add `test` and `vitest`.

- [ ] **Step 2: Install the frontend test dependency**

Run:

```bash
cd frontend
npm install
```

Expected: `package-lock.json` updates and `node_modules/vitest` exists.

- [ ] **Step 3: Write failing API client tests**

Create `frontend/src/api/__tests__/client.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { ApiError, createApiClient } from '../client'

describe('createApiClient', () => {
  it('sends JSON requests with X-User-Id and unwraps data', async () => {
    const calls: RequestInit[] = []
    const client = createApiClient({
      baseUrl: 'http://api.test/api/v1',
      userId: 'user-1',
      fetchImpl: async (_input, init) => {
        calls.push(init ?? {})
        return new Response(JSON.stringify({ code: 200, message: 'ok', data: { value: 42 } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      },
    })

    const data = await client.request<{ value: number }>('/demo', {
      method: 'POST',
      body: { hello: 'world' },
    })

    expect(data).toEqual({ value: 42 })
    expect(calls[0].headers).toMatchObject({
      'Content-Type': 'application/json',
      'X-User-Id': 'user-1',
    })
    expect(calls[0].body).toBe(JSON.stringify({ hello: 'world' }))
  })

  it('throws ApiError with backend message on business failure', async () => {
    const client = createApiClient({
      baseUrl: '/api/v1',
      userId: 'user-1',
      fetchImpl: async () =>
        new Response(JSON.stringify({ code: 40101, message: '缺少用户身份标识' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
    })

    await expect(client.request('/demo')).rejects.toMatchObject<ApiError>({
      name: 'ApiError',
      status: 401,
      code: 40101,
      message: '缺少用户身份标识',
    })
  })
})
```

- [ ] **Step 4: Write failing mapper tests**

Create `frontend/src/api/__tests__/mappers.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import {
  mapPreferencesToSettings,
  mapProfile,
  mapSessionToConversation,
  mapSessionToTravelHistory,
  mapSnapshotToTripSummary,
} from '../mappers'

describe('API mappers', () => {
  it('maps user profile fields from snake case to camel case', () => {
    expect(
      mapProfile({
        avatar_url: '',
        nickname: 'Ada',
        username: 'ada',
        email: 'ada@example.com',
        current_city: '北京',
      }),
    ).toEqual({
      avatarUrl: '',
      nickname: 'Ada',
      username: 'ada',
      email: 'ada@example.com',
      currentCity: '北京',
    })
  })

  it('maps session summary to conversation and travel history cards', () => {
    const session = {
      thread_id: 'thread-1',
      destination: '北京',
      start_date: '2026-08-10',
      duration: 3,
      status: 'confirmed' as const,
      last_updated: '2026-08-03T10:00:00Z',
    }

    expect(mapSessionToConversation(session)).toMatchObject({
      id: 'thread-1',
      title: '北京 3日游',
      status: '进行中',
    })
    expect(mapSessionToTravelHistory(session)).toMatchObject({
      id: 'thread-1',
      destination: '北京',
      title: '北京 3日游',
      dateRange: '2026.8.10 - 2026.8.12',
      people: 1,
      totalExpenseCny: 0,
    })
  })

  it('maps preferences into editable settings', () => {
    const settings = mapPreferencesToSettings([
      {
        id: 'pref-1',
        category: 'diet',
        content: '不吃海鲜',
        source: 'manual',
        confidence: 1,
        is_active: true,
      },
      {
        id: 'pref-2',
        category: 'budget',
        content: '舒适出行',
        source: 'manual',
        confidence: 1,
        is_active: true,
      },
    ])

    expect(settings.dietaryPreferences).toContain('不吃海鲜')
    expect(settings.budgetPreference).toBe('舒适出行')
  })

  it('maps snapshot budget fields into trip summary', () => {
    const trip = mapSnapshotToTripSummary({
      session_id: 'thread-1',
      state: {
        blackboard: {
          destination: '北京',
          start_date: '2026-08-10',
          duration: 3,
          structured_preferences: { travelers: 2, budget_max_total: 5000 },
          budget: { total: 3200 },
        },
        task_list: [],
      },
      graph_structure: { nodes: [], edges: [] },
      metadata: {},
      created_at: '2026-08-03T10:00:00Z',
    })

    expect(trip).toEqual({
      title: '北京 3日游',
      dateRange: '2026.8.10 - 2026.8.12',
      people: 2,
      budgetCny: 5000,
      spentCny: 3200,
    })
  })
})
```

- [ ] **Step 5: Write failing SSE parser tests**

Create `frontend/src/api/__tests__/chat.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import { parseSseMessages } from '../chat'

describe('parseSseMessages', () => {
  it('parses complete SSE events and returns remaining partial text', () => {
    const result = parseSseMessages(
      'event: node\ndata: {"node":"itinerary_agent"}\n\nevent: done\ndata: {"thread_id":"t1"}\n\nevent: error',
    )

    expect(result.events).toEqual([
      { event: 'node', data: { node: 'itinerary_agent' } },
      { event: 'done', data: { thread_id: 't1' } },
    ])
    expect(result.rest).toBe('event: error')
  })
})
```

- [ ] **Step 6: Run frontend tests and verify red**

Run:

```bash
cd frontend
npm test
```

Expected: FAIL because `src/api/client`, `src/api/mappers`, and `src/api/chat` are not implemented.

- [ ] **Step 7: Add backend wire types**

Create `frontend/src/api/types.ts`:

```typescript
export type ApiResponse<T> = {
  code: number
  message: string
  data: T
}

export type ErrorResponse = {
  code: number
  message: string
  details?: unknown
}

export type UserProfileData = {
  avatar_url: string
  nickname: string
  username: string
  email: string
  current_city: string
}

export type SessionStatus = 'planning' | 'confirmed' | 'completed' | 'deleted'

export type SessionItem = {
  thread_id: string
  destination: string | null
  start_date: string | null
  duration: number | null
  status: SessionStatus
  last_updated: string
}

export type SessionListData = {
  sessions: SessionItem[]
  next_cursor: string | null
  has_more: boolean
}

export type SessionSnapshotData = {
  session_id: string
  state: {
    task_list?: unknown[]
    blackboard?: Record<string, unknown>
  }
  graph_structure: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: string
}

export type PreferenceCategory = 'diet' | 'pace' | 'budget' | 'interest' | 'accommodation' | 'transport'
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

export type PreferenceListData = {
  preferences: PreferenceItem[]
  summary: {
    total: number
    active_count: number
    categories: Record<string, number>
  }
}

export type ChatStreamRequest = {
  thread_id: string
  message: string
  current_time?: string
  structured_input?: Record<string, unknown>
}

export type ParsedSseEvent = {
  event: string
  data: unknown
}
```

- [ ] **Step 8: Add the API client**

Create `frontend/src/api/client.ts`:

```typescript
import type { ApiResponse, ErrorResponse } from './types'

type FetchLike = typeof fetch

type ClientOptions = {
  baseUrl: string
  userId: string
  fetchImpl?: FetchLike
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
}

export class ApiError extends Error {
  status: number
  code?: number
  details?: unknown

  constructor(message: string, status: number, code?: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function apiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL || '/api/v1'
}

function travelmateUserId() {
  return import.meta.env.VITE_TRAVELMATE_USER_ID || 'demo-user'
}

function buildUrl(baseUrl: string, path: string) {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as Partial<ErrorResponse>
    return new ApiError(body.message || response.statusText, response.status, body.code, body.details)
  } catch {
    return new ApiError(response.statusText || 'Request failed', response.status)
  }
}

export function createApiClient(options: ClientOptions) {
  const fetchImpl = options.fetchImpl ?? fetch

  async function raw(path: string, init: RequestOptions = {}) {
    const headers: Record<string, string> = {
      'X-User-Id': options.userId,
      ...(init.headers as Record<string, string> | undefined),
    }

    let body: BodyInit | undefined
    if (init.body !== undefined) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json'
      body = typeof init.body === 'string' ? init.body : JSON.stringify(init.body)
    }

    const response = await fetchImpl(buildUrl(options.baseUrl, path), {
      ...init,
      headers,
      body,
    })

    if (!response.ok) {
      throw await parseError(response)
    }

    return response
  }

  async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const response = await raw(path, init)
    const body = (await response.json()) as ApiResponse<T>
    if (body.code >= 400) {
      throw new ApiError(body.message, response.status, body.code)
    }
    return body.data
  }

  return { raw, request }
}

export const apiClient = createApiClient({
  baseUrl: apiBaseUrl(),
  userId: travelmateUserId(),
})
```

- [ ] **Step 9: Add API wrapper modules**

Create `frontend/src/api/users.ts`:

```typescript
import { apiClient } from './client'
import type { UserProfileData } from './types'

export function fetchUserProfile() {
  return apiClient.request<UserProfileData>('/users/me/profile')
}
```

Create `frontend/src/api/preferences.ts`:

```typescript
import { apiClient } from './client'
import type { PreferenceCategory, PreferenceItem, PreferenceListData } from './types'

export function fetchPreferences() {
  return apiClient.request<PreferenceListData>('/users/me/preferences')
}

export function addPreference(category: PreferenceCategory, content: string) {
  return apiClient.request<PreferenceItem>('/users/me/preferences', {
    method: 'POST',
    body: { category, content },
  })
}

export function updatePreference(preferenceId: string, content: string) {
  return apiClient.request<PreferenceItem>(`/users/me/preferences/${preferenceId}`, {
    method: 'PUT',
    body: { content },
  })
}

export function deletePreference(preferenceId: string) {
  return apiClient.request<{ id: string; is_active: boolean; deleted_at: string }>(
    `/users/me/preferences/${preferenceId}`,
    { method: 'DELETE' },
  )
}
```

Create `frontend/src/api/sessions.ts`:

```typescript
import { apiClient } from './client'
import type { SessionListData, SessionSnapshotData } from './types'

export function fetchSessions(limit = 20, cursor?: string | null) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (cursor) params.set('cursor', cursor)
  return apiClient.request<SessionListData>(`/sessions?${params.toString()}`)
}

export function fetchSessionSnapshot(sessionId: string) {
  return apiClient.request<SessionSnapshotData>(`/sessions/${encodeURIComponent(sessionId)}/snapshot`)
}

export async function deleteSession(sessionId: string) {
  await apiClient.raw(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}
```

- [ ] **Step 10: Add chat SSE parsing and stream wrapper**

Create `frontend/src/api/chat.ts`:

```typescript
import { apiClient } from './client'
import type { ChatStreamRequest, ParsedSseEvent } from './types'

type ParseResult = {
  events: ParsedSseEvent[]
  rest: string
}

export function parseSseMessages(text: string): ParseResult {
  const parts = text.split('\n\n')
  const rest = parts.pop() ?? ''
  const events = parts
    .map((part) => {
      const eventLine = part.split('\n').find((line) => line.startsWith('event: '))
      const dataLine = part.split('\n').find((line) => line.startsWith('data: '))
      if (!eventLine || !dataLine) return null
      return {
        event: eventLine.slice('event: '.length),
        data: JSON.parse(dataLine.slice('data: '.length)),
      }
    })
    .filter((event): event is ParsedSseEvent => event !== null)
  return { events, rest }
}

export async function streamChat(
  request: ChatStreamRequest,
  onEvent: (event: ParsedSseEvent) => void,
) {
  const response = await apiClient.raw('/chat/stream', {
    method: 'POST',
    body: request,
  })
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let rest = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    const parsed = parseSseMessages(rest + decoder.decode(value, { stream: true }))
    rest = parsed.rest
    parsed.events.forEach(onEvent)
  }
}
```

- [ ] **Step 11: Add mapper implementations**

Create `frontend/src/api/mappers.ts`:

```typescript
import type { Conversation, ExpenseCategory, ItineraryItem, TripSummary } from '../types/chat'
import type { TravelHistory } from '../types/history'
import type { GeneralSettings, PreferenceSettings, UserProfile } from '../types/profile'
import { img } from '../utils/image'
import type { PreferenceItem, SessionItem, SessionSnapshotData, UserProfileData } from './types'

const defaultPreferenceSettings: PreferenceSettings = {
  travelTypes: [],
  budgetPreference: '舒适出行',
  transportPreference: '飞机',
  dietaryPreferences: [],
  customPreferences: [],
}

export const defaultGeneralSettings: GeneralSettings = {
  theme: '浅色',
  language: '中文',
}

export function mapProfile(profile: UserProfileData): UserProfile {
  return {
    avatarUrl: profile.avatar_url,
    nickname: profile.nickname,
    username: profile.username,
    email: profile.email,
    currentCity: profile.current_city,
  }
}

function formatDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  return `${date.getFullYear()}.${date.getMonth() + 1}.${date.getDate()}`
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

function dateRange(startDate?: string | null, duration?: number | null) {
  if (!startDate || !duration) return '日期未设置'
  return `${formatDate(startDate)} - ${formatDate(addDays(startDate, Math.max(1, duration) - 1))}`
}

function title(destination?: string | null, duration?: number | null) {
  return destination ? `${destination} ${duration || 1}日游` : '未命名行程'
}

function conversationStatus(status: SessionItem['status']): Conversation['status'] {
  return status === 'completed' || status === 'deleted' ? '已完成' : '进行中'
}

function historyStatus(status: SessionItem['status']): TravelHistory['status'] {
  if (status === 'completed') return '已完成'
  if (status === 'deleted') return '已归档'
  return '进行中'
}

export function mapSessionToConversation(session: SessionItem): Conversation {
  return {
    id: session.thread_id,
    title: title(session.destination, session.duration),
    updatedAt: new Date(session.last_updated).toLocaleString('zh-CN'),
    status: conversationStatus(session.status),
  }
}

export function mapSessionToTravelHistory(session: SessionItem): TravelHistory {
  const destination = session.destination || '目的地未设置'
  return {
    id: session.thread_id,
    destination,
    title: title(session.destination, session.duration),
    status: historyStatus(session.status),
    dateRange: dateRange(session.start_date, session.duration),
    people: 1,
    coverImageUrl: img(`${destination} travel landmark`, 'landscape_4_3'),
    totalExpenseCny: 0,
    routeItems: [],
    dailyExpenses: [],
    categoryExpenses: [],
    expenseDetails: [],
  }
}

export function mapPreferencesToSettings(preferences: PreferenceItem[]): PreferenceSettings {
  return preferences.filter((item) => item.is_active).reduce<PreferenceSettings>((settings, item) => {
    if (item.category === 'interest') settings.travelTypes = [...settings.travelTypes, item.content as never]
    else if (item.category === 'diet') settings.dietaryPreferences = [...settings.dietaryPreferences, item.content as never]
    else if (item.category === 'budget') settings.budgetPreference = item.content as never
    else if (item.category === 'transport') settings.transportPreference = item.content as never
    else settings.customPreferences = [...settings.customPreferences, item.content]
    return settings
  }, { ...defaultPreferenceSettings })
}

function blackboard(snapshot: SessionSnapshotData) {
  return snapshot.state.blackboard ?? {}
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === 'number' ? value : fallback
}

export function mapSnapshotToTripSummary(snapshot: SessionSnapshotData): TripSummary {
  const state = blackboard(snapshot)
  const prefs = (state.structured_preferences ?? {}) as Record<string, unknown>
  const budget = (state.budget ?? state.draft_budget ?? {}) as Record<string, unknown>
  const destination = typeof state.destination === 'string' ? state.destination : '未命名行程'
  const duration = numberValue(state.duration, 1)
  const startDate = typeof state.start_date === 'string' ? state.start_date : null

  return {
    title: title(destination, duration),
    dateRange: dateRange(startDate, duration),
    people: numberValue(prefs.travelers, 1),
    budgetCny: numberValue(prefs.budget_max_total, numberValue(budget.max_total, 0)),
    spentCny: numberValue(budget.total, 0),
  }
}

export function mapSnapshotToItinerary(snapshot: SessionSnapshotData): ItineraryItem[] {
  const source = blackboard(snapshot).daily_itinerary ?? blackboard(snapshot).draft_daily_itinerary
  if (!Array.isArray(source)) return []
  return source.map((item, index) => {
    const value = item as Record<string, unknown>
    const name = String(value.attractionName ?? value.attraction_name ?? value.name ?? `行程 ${index + 1}`)
    return {
      id: String(value.id ?? `itinerary-${index}`),
      date: String(value.date ?? ''),
      attractionName: name,
      timeRange: String(value.timeRange ?? value.time_range ?? value.time ?? ''),
      priceCny: numberValue(value.priceCny ?? value.price_cny ?? value.cost, 0),
      status: '待确认',
      category: '景点',
      imageUrl: img(`${name} travel`, 'landscape_4_3'),
    } as ItineraryItem
  })
}

export function mapSnapshotToExpenses(snapshot: SessionSnapshotData): ExpenseCategory[] {
  const budget = (blackboard(snapshot).budget ?? blackboard(snapshot).draft_budget ?? {}) as Record<string, unknown>
  const categories = budget.categories
  if (!Array.isArray(categories)) return []
  return categories.map((item, index) => {
    const value = item as Record<string, unknown>
    return {
      name: String(value.name ?? `费用 ${index + 1}`),
      amount: numberValue(value.amount ?? value.amountCny ?? value.amount_cny, 0),
      color: String(value.color ?? ['#0071EB', '#FF6F61', '#10B981', '#F59E0B'][index % 4]),
    }
  })
}
```

- [ ] **Step 12: Run frontend tests and verify green**

Run:

```bash
cd frontend
npm test
```

Expected: PASS with all API tests passing.

- [ ] **Step 13: Commit Task 3**

Run:

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api
git commit -m "feat: add frontend API layer"
```

---

### Task 4: Profile and Preferences Real API Integration

**Files:**
- Modify: `frontend/src/hooks/useProfilePageData.ts`
- Modify: `frontend/src/components/common/AppHeader.tsx`
- Modify: `frontend/src/components/profile/ProfileOutletPanel.tsx`
- Modify: `frontend/src/components/profile/TravelHistoryOutlet.tsx`

- [ ] **Step 1: Write a mapper regression test for empty profile fallback**

Append this test to `frontend/src/api/__tests__/mappers.test.ts`:

```typescript
it('keeps empty profile fields empty so components can show neutral fallbacks', () => {
  expect(
    mapProfile({
      avatar_url: '',
      nickname: '',
      username: 'demo-user',
      email: '',
      current_city: '',
    }),
  ).toEqual({
    avatarUrl: '',
    nickname: '',
    username: 'demo-user',
    email: '',
    currentCity: '',
  })
})
```

- [ ] **Step 2: Run the focused mapper test and verify red if import coverage is missing**

Run:

```bash
cd frontend
npm test -- src/api/__tests__/mappers.test.ts
```

Expected: PASS if Task 3 already exported `mapProfile`; otherwise FAIL with a missing import or assertion mismatch. Fix only mapper exports before proceeding.

- [ ] **Step 3: Replace profile hook mock imports with API calls**

Modify `frontend/src/hooks/useProfilePageData.ts` so it no longer imports `profileData` or `historyData`:

```typescript
import { useEffect, useMemo, useState } from 'react'
import { fetchPreferences } from '../api/preferences'
import { fetchSessions } from '../api/sessions'
import { fetchUserProfile } from '../api/users'
import {
  defaultGeneralSettings,
  mapPreferencesToSettings,
  mapProfile,
  mapSessionToTravelHistory,
} from '../api/mappers'
import type { TravelHistory } from '../types/history'
import type { GeneralSettings, PreferenceSettings, UserProfile } from '../types/profile'
import { getProfileTravelStats } from '../utils/profileStats'

const emptyProfile: UserProfile = {
  avatarUrl: '',
  nickname: '',
  username: 'demo-user',
  email: '',
  currentCity: '',
}

const emptyPreferences: PreferenceSettings = {
  travelTypes: [],
  budgetPreference: '舒适出行',
  transportPreference: '飞机',
  dietaryPreferences: [],
  customPreferences: [],
}

export function useProfilePageData() {
  const [preferences, setPreferences] = useState<PreferenceSettings>(emptyPreferences)
  const [settings, setSettings] = useState<GeneralSettings>(defaultGeneralSettings)
  const [profile, setProfile] = useState<UserProfile>(emptyProfile)
  const [histories, setHistories] = useState<TravelHistory[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadProfilePageData() {
      setIsLoading(true)
      setError(null)
      try {
        const [profileData, preferencesData, sessionsData] = await Promise.all([
          fetchUserProfile(),
          fetchPreferences(),
          fetchSessions(),
        ])
        if (cancelled) return
        setProfile(mapProfile(profileData))
        setPreferences(mapPreferencesToSettings(preferencesData.preferences))
        setHistories(sessionsData.sessions.map(mapSessionToTravelHistory))
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载失败')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void loadProfilePageData()
    return () => {
      cancelled = true
    }
  }, [])

  const profileStats = useMemo(() => getProfileTravelStats(histories), [histories])

  return {
    error,
    histories,
    isLoading,
    preferences,
    profile,
    profileStats,
    setPreferences,
    setSettings,
    settings,
  }
}

export type ProfilePageData = ReturnType<typeof useProfilePageData>
```

- [ ] **Step 4: Update AppHeader to fetch real profile**

Modify `frontend/src/components/common/AppHeader.tsx`:

```typescript
import { Avatar, Button, Layout } from 'antd'
import { HistoryOutlined, SettingOutlined, SlidersOutlined, UserOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchUserProfile } from '../../api/users'
import { mapProfile } from '../../api/mappers'
import type { UserProfile } from '../../types/profile'
import type { TravelmateTheme } from '../../utils/theme.tsx'

const { Header } = Layout

type AppHeaderProps = {
  colors: TravelmateTheme
}

const neutralProfile: UserProfile = {
  avatarUrl: '',
  nickname: '',
  username: 'demo-user',
  email: '',
  currentCity: '',
}

export function AppHeader({ colors }: AppHeaderProps) {
  const navigate = useNavigate()
  const [profile, setProfile] = useState<UserProfile>(neutralProfile)

  useEffect(() => {
    let cancelled = false
    fetchUserProfile()
      .then((data) => {
        if (!cancelled) setProfile(mapProfile(data))
      })
      .catch(() => {
        if (!cancelled) setProfile(neutralProfile)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const displayName = profile.username || profile.nickname || 'demo-user'

  return (
    <Header
      style={{ height: 72, padding: '0 20px', backgroundColor: '#ffffff', lineHeight: 'normal' }}
      className="flex items-center justify-between bg-white shadow-sm"
    >
      <button
        type="button"
        className="flex items-center gap-3 text-left"
        onClick={() => navigate('/chat')}
        aria-label="返回聊天首页"
      >
        <div
          className="h-9 w-9 rounded-xl shadow-sm"
          style={{ backgroundImage: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primary2} 100%)` }}
        />
        <div className="flex flex-col leading-tight">
          <div className="text-[16px] font-semibold text-slate-900">Travelmate</div>
          <div className="text-[12px] text-slate-500">AI Travel Assistant</div>
        </div>
      </button>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="ml-2 flex items-center gap-2 rounded-full px-2 py-1 transition-colors hover:bg-slate-50"
          onClick={() => navigate('/profile/preferences')}
          aria-label="打开个人中心"
        >
          <Avatar size={36} src={profile.avatarUrl || undefined} icon={<UserOutlined />} className="bg-slate-200 text-slate-700" />
          <span className="max-w-[140px] truncate text-[14px] font-medium text-slate-700">{displayName}</span>
        </button>
        <Button type="text" icon={<HistoryOutlined />} className="text-slate-700" onClick={() => navigate('/history')}>
          History
        </Button>
        <Button
          type="text"
          icon={<SlidersOutlined />}
          className="text-slate-700"
          onClick={() => navigate('/profile/preferences')}
        >
          Preferences
        </Button>
        <Button
          type="text"
          icon={<SettingOutlined />}
          className="text-slate-700"
          onClick={() => navigate('/profile/settings')}
        >
          Settings
        </Button>
      </div>
    </Header>
  )
}
```

- [ ] **Step 5: Pass real histories through profile outlet context**

Modify `frontend/src/layouts/ProfileLayout.tsx` outlet context to include `histories`, `isLoading`, and `error` from `ProfilePageData`.

Modify `frontend/src/components/profile/ProfileOutletPanel.tsx`:

```typescript
const { histories, preferences, profile, setPreferences, setSettings, settings } = useOutletContext<ProfilePageData>()

const panel =
  outletKey === 'settings' ? (
    <SettingsOutlet profile={profile} settings={settings} setSettings={setSettings} />
  ) : outletKey === 'history' ? (
    <TravelHistoryOutlet histories={histories} />
  ) : (
    <PreferencesOutlet preferences={preferences} setPreferences={setPreferences} />
  )
```

Modify `frontend/src/components/profile/TravelHistoryOutlet.tsx` to accept props:

```typescript
import { Empty, Card, List, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { formatCurrencyCny } from '../../utils/historyFormat'

type TravelHistoryOutletProps = {
  histories: TravelHistory[]
}

export function TravelHistoryOutlet({ histories }: TravelHistoryOutletProps) {
  return (
    <Card
      className="flex h-full flex-col rounded-2xl border-0 shadow-sm"
      title="旅行历史"
      styles={{ body: { flex: 1, minHeight: 0, overflowY: 'auto', padding: 0 } }}
    >
      {histories.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史行程" className="py-12" />
      ) : (
        <List
          dataSource={histories}
          renderItem={(history) => (
            <List.Item className="px-5 py-4">
              <List.Item.Meta
                avatar={<img src={history.coverImageUrl} alt={history.title} className="h-16 w-24 rounded-lg object-cover" />}
                title={<span className="font-semibold text-slate-900">{history.title}</span>}
                description={
                  <span className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                    <span>{history.destination}</span>
                    <span>{history.dateRange}</span>
                    <span>{history.people} 人出行</span>
                  </span>
                }
              />
              <div className="flex shrink-0 flex-col items-end gap-2">
                <Tag className="m-0 rounded-full">{history.status}</Tag>
                <span className="text-[13px] font-semibold text-slate-900">{formatCurrencyCny(history.totalExpenseCny)}</span>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
```

- [ ] **Step 6: Run frontend build for profile integration**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS or expose exact TypeScript errors to fix in the modified profile files.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add frontend/src/hooks/useProfilePageData.ts frontend/src/components/common/AppHeader.tsx frontend/src/layouts/ProfileLayout.tsx frontend/src/components/profile/ProfileOutletPanel.tsx frontend/src/components/profile/TravelHistoryOutlet.tsx frontend/src/api/__tests__/mappers.test.ts
git commit -m "feat: load profile data from APIs"
```

---

### Task 5: History Page Real API Integration

**Files:**
- Modify: `frontend/src/hooks/useHistoryPageData.ts`
- Modify: `frontend/src/layouts/HistoryLayout.tsx`
- Modify: `frontend/src/components/history/HistoryDetailPanel.tsx`

- [ ] **Step 1: Write a history empty-state type check through build**

Modify `frontend/src/components/history/HistoryDetailPanel.tsx` prop type first:

```typescript
type HistoryDetailPanelProps = {
  history: TravelHistory | undefined
}
```

Run:

```bash
cd frontend
npm run build
```

Expected: FAIL because the component still dereferences `history` without guarding.

- [ ] **Step 2: Load histories and snapshots from backend**

Replace `frontend/src/hooks/useHistoryPageData.ts` with:

```typescript
import { useEffect, useMemo, useState } from 'react'
import { fetchSessions, fetchSessionSnapshot } from '../api/sessions'
import { mapSessionToTravelHistory, mapSnapshotToExpenses, mapSnapshotToItinerary, mapSnapshotToTripSummary } from '../api/mappers'
import type { TravelHistory } from '../types/history'

export function useHistoryPageData() {
  const [histories, setHistories] = useState<TravelHistory[]>([])
  const [selectedHistoryId, setSelectedHistoryId] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadSessions() {
      setIsLoading(true)
      setError(null)
      try {
        const data = await fetchSessions()
        if (cancelled) return
        const mapped = data.sessions.map(mapSessionToTravelHistory)
        setHistories(mapped)
        setSelectedHistoryId((current) => current || mapped[0]?.id || '')
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载历史失败')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void loadSessions()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedHistoryId) return
    let cancelled = false

    async function loadSnapshot() {
      try {
        const snapshot = await fetchSessionSnapshot(selectedHistoryId)
        if (cancelled) return
        const trip = mapSnapshotToTripSummary(snapshot)
        setHistories((current) =>
          current.map((history) =>
            history.id === selectedHistoryId
              ? {
                  ...history,
                  title: trip.title,
                  dateRange: trip.dateRange,
                  people: trip.people,
                  totalExpenseCny: trip.spentCny,
                  routeItems: mapSnapshotToItinerary(snapshot).map((item) => ({
                    id: item.id,
                    imageUrl: item.imageUrl,
                    attractionName: item.attractionName,
                    time: `${item.date} ${item.timeRange}`.trim(),
                    costCny: item.priceCny,
                    description: item.category,
                  })),
                  categoryExpenses: mapSnapshotToExpenses(snapshot).map((item) => ({
                    name: item.name,
                    amountCny: item.amount,
                    color: item.color,
                  })),
                }
              : history,
          ),
        )
      } catch {
        if (!cancelled) {
          setHistories((current) => current.map((history) => (history.id === selectedHistoryId ? history : history)))
        }
      }
    }

    void loadSnapshot()
    return () => {
      cancelled = true
    }
  }, [selectedHistoryId])

  const selectedHistory = useMemo(
    () => histories.find((history) => history.id === selectedHistoryId) ?? histories[0],
    [histories, selectedHistoryId],
  )

  return {
    error,
    histories,
    isLoading,
    selectedHistory,
    selectedHistoryId,
    setSelectedHistoryId,
  }
}

export type HistoryPageData = ReturnType<typeof useHistoryPageData>
```

- [ ] **Step 3: Add empty and loading states to history layout**

Modify `frontend/src/layouts/HistoryLayout.tsx`:

```typescript
import { Empty, Layout, Spin } from 'antd'
import { HistoryDetailPanel } from '../components/history/HistoryDetailPanel'
import { TravelHistorySidebar } from '../components/history/TravelHistorySidebar'
import type { HistoryPageData } from '../hooks/useHistoryPageData'

const { Content } = Layout

type HistoryLayoutProps = HistoryPageData

export function HistoryLayout({ error, histories, isLoading, selectedHistory, selectedHistoryId, setSelectedHistoryId }: HistoryLayoutProps) {
  if (isLoading) {
    return (
      <Content className="flex h-[calc(100vh-72px)] items-center justify-center">
        <Spin />
      </Content>
    )
  }

  if (error && histories.length === 0) {
    return (
      <Content className="flex h-[calc(100vh-72px)] items-center justify-center">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={error} />
      </Content>
    )
  }

  return (
    <Content className="h-[calc(100vh-72px)] overflow-hidden">
      <div className="flex h-full">
        <TravelHistorySidebar histories={histories} onSelectHistory={setSelectedHistoryId} selectedHistoryId={selectedHistoryId} />
        <HistoryDetailPanel history={selectedHistory} />
      </div>
    </Content>
  )
}
```

Modify `frontend/src/components/history/HistoryDetailPanel.tsx` to guard empty history:

```typescript
import { Empty } from 'antd'
import type { TravelHistory } from '../../types/history'
import { useHistoryOutletStore } from '../../store/useHistoryOutletStore'
import type { HistoryOutletKey } from '../../types/history'
import { HistoryMapCard } from './HistoryMapCard'
import { HistoryOutletPanel } from './HistoryOutletPanel'
import { HistoryTripInfoCard } from './HistoryTripInfoCard'

type HistoryDetailPanelProps = {
  history: TravelHistory | undefined
}

export function HistoryDetailPanel({ history }: HistoryDetailPanelProps) {
  const activeOutlet = useHistoryOutletStore((state) => state.activeOutlet)
  const showRoute = useHistoryOutletStore((state) => state.showRoute)
  const showExpense = useHistoryOutletStore((state) => state.showExpense)
  const setActiveOutlet = (outlet: HistoryOutletKey) => {
    if (outlet === 'route') showRoute()
    else showExpense()
  }

  if (!history) {
    return (
      <section className="flex min-w-0 flex-1 items-center justify-center bg-slate-50 p-6">
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史行程" />
      </section>
    )
  }

  return (
    <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6">
      <div className="mx-auto flex max-w-[1040px] flex-col gap-5">
        <HistoryMapCard history={history} />
        <HistoryTripInfoCard activeOutlet={activeOutlet} history={history} onOutletChange={setActiveOutlet} />
        <HistoryOutletPanel activeOutlet={activeOutlet} history={history} />
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: both commands PASS.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add frontend/src/hooks/useHistoryPageData.ts frontend/src/layouts/HistoryLayout.tsx frontend/src/components/history/HistoryDetailPanel.tsx
git commit -m "feat: load history from session APIs"
```

---

### Task 6: Chat Stream Real API Integration

**Files:**
- Modify: `frontend/src/hooks/useChatPageState.ts`
- Modify: `frontend/src/layouts/ChatLayout.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`

- [ ] **Step 1: Add request mapping helpers for structured chat input**

Create `frontend/src/api/chatRequest.ts`:

```typescript
import type { StructuredPreferences } from '../types/chat'

const budgetMap = {
  经济实惠: 'economy',
  舒适出行: 'mid',
  奢华体验: 'luxury',
} as const

const paceMap = {
  轻松: 'relaxed',
  适中: 'relaxed',
  紧凑: 'intensive',
} as const

export function toStructuredInput(message: string, preferences?: StructuredPreferences) {
  if (!preferences) return undefined
  return {
    destination: message,
    duration: 1,
    budget: {
      level: preferences.budget_level ? budgetMap[preferences.budget_level as keyof typeof budgetMap] ?? 'mid' : 'mid',
    },
    hotel_preference: preferences.hotel_preference,
    intercity_transport: preferences.intercity_transport ? [preferences.intercity_transport] : [],
    local_transport: preferences.local_transport ? [preferences.local_transport] : [],
    pace: preferences.pace ? paceMap[preferences.pace as keyof typeof paceMap] ?? 'relaxed' : 'relaxed',
    interests: preferences.interests ?? [],
    travelers: preferences.travelers ?? 1,
    travelers_type: 'adult',
  }
}
```

Add a test in `frontend/src/api/__tests__/chat.test.ts`:

```typescript
import { toStructuredInput } from '../chatRequest'

it('maps structured preferences into backend structured input', () => {
  expect(toStructuredInput('北京三日游', { budget_level: '舒适出行', travelers: 2 })).toMatchObject({
    destination: '北京三日游',
    duration: 1,
    budget: { level: 'mid' },
    travelers: 2,
  })
})
```

- [ ] **Step 2: Run chat tests and verify red**

Run:

```bash
cd frontend
npm test -- src/api/__tests__/chat.test.ts
```

Expected: FAIL until `chatRequest.ts` is created and exported correctly.

- [ ] **Step 3: Replace chat hook mock imports with session and stream APIs**

Modify `frontend/src/hooks/useChatPageState.ts`:

```typescript
import { useEffect, useMemo, useState } from 'react'
import { streamChat } from '../api/chat'
import { toStructuredInput } from '../api/chatRequest'
import { fetchSessions, fetchSessionSnapshot } from '../api/sessions'
import {
  mapSessionToConversation,
  mapSnapshotToExpenses,
  mapSnapshotToItinerary,
  mapSnapshotToTripSummary,
} from '../api/mappers'
import type { ChatMessage, Conversation, ExpenseCategory, ItineraryItem, StructuredPreferences, TripSummary } from '../types/chat'
import { groupItineraryByDate } from '../utils/itinerary'
import { buildPieConicGradient } from '../utils/pie'
import { travelmateTheme } from '../utils/theme.tsx'

function formatMessageTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function createThreadId() {
  return `thread_${Date.now()}`
}

const emptyTrip: TripSummary = {
  title: '未命名行程',
  dateRange: '日期未设置',
  people: 1,
  budgetCny: 0,
  spentCny: 0,
}

export function useChatPageState() {
  const colors = travelmateTheme
  const [siderCollapsed, setSiderCollapsed] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [selectedDateIndex, setSelectedDateIndex] = useState(0)
  const [structuredPreferences, setStructuredPreferences] = useState<StructuredPreferences>()
  const [isNewTripMode, setIsNewTripMode] = useState(true)
  const [isStreaming, setIsStreaming] = useState(false)
  const [itinerary, setItinerary] = useState<ItineraryItem[]>([])
  const [trip, setTrip] = useState<TripSummary>(emptyTrip)
  const [expensesByCategory, setExpensesByCategory] = useState<ExpenseCategory[]>([])

  useEffect(() => {
    let cancelled = false
    fetchSessions()
      .then((data) => {
        if (cancelled) return
        const mapped = data.sessions.map(mapSessionToConversation)
        setConversations(mapped)
        setActiveConversationId(mapped[0]?.id ?? '')
        setIsNewTripMode(mapped.length === 0)
      })
      .catch(() => {
        if (!cancelled) setIsNewTripMode(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!activeConversationId) return
    let cancelled = false
    fetchSessionSnapshot(activeConversationId)
      .then((snapshot) => {
        if (cancelled) return
        setTrip(mapSnapshotToTripSummary(snapshot))
        setItinerary(mapSnapshotToItinerary(snapshot))
        setExpensesByCategory(mapSnapshotToExpenses(snapshot))
      })
      .catch(() => {
        if (!cancelled) {
          setTrip(emptyTrip)
          setItinerary([])
          setExpensesByCategory([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [activeConversationId])

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0],
    [activeConversationId, conversations],
  )
  const itineraryGroupedByDate = useMemo(() => groupItineraryByDate(itinerary), [itinerary])
  const datesList = useMemo(() => Object.keys(itineraryGroupedByDate), [itineraryGroupedByDate])
  const activeDate = datesList[selectedDateIndex] || datesList[0] || ''
  const currentItems = itineraryGroupedByDate[activeDate] || []
  const remaining = Math.max(0, trip.budgetCny - trip.spentCny)
  const pieConicGradient = useMemo(() => buildPieConicGradient(expensesByCategory), [expensesByCategory])

  function startNewTrip() {
    setIsNewTripMode(true)
    setActiveConversationId('')
    setMessages([])
    setDraft('')
    setStructuredPreferences(undefined)
    setSelectedDateIndex(0)
    setTrip(emptyTrip)
    setItinerary([])
    setExpensesByCategory([])
  }

  function selectConversation(conversationId: string) {
    setActiveConversationId(conversationId)
    setIsNewTripMode(false)
    setMessages([])
  }

  async function sendMessage() {
    const content = draft.trim()
    if (!content || isStreaming) return

    const threadId = activeConversationId || createThreadId()
    setIsNewTripMode(false)
    setActiveConversationId(threadId)
    setConversations((current) =>
      current.some((conversation) => conversation.id === threadId)
        ? current
        : [{ id: threadId, title: content.slice(0, 20), updatedAt: '刚刚', status: '进行中' }, ...current],
    )

    const nextUser: ChatMessage = {
      id: `m-${Date.now()}`,
      role: 'user',
      content,
      time: formatMessageTime(),
      ...(structuredPreferences ? { structured_preferences: structuredPreferences } : {}),
    }
    const assistantId = `m-a-${Date.now()}`
    setMessages((previous) => [
      ...previous,
      nextUser,
      { id: assistantId, role: 'assistant', content: '正在生成行程...', time: formatMessageTime() },
    ])
    setDraft('')
    setIsStreaming(true)

    try {
      await streamChat(
        {
          thread_id: threadId,
          message: content,
          current_time: new Date().toISOString(),
          structured_input: toStructuredInput(content, structuredPreferences),
        },
        (event) => {
          if (event.event === 'node') {
            setMessages((previous) =>
              previous.map((message) =>
                message.id === assistantId
                  ? { ...message, content: `${message.content}\n${JSON.stringify(event.data)}` }
                  : message,
              ),
            )
          }
          if (event.event === 'done') {
            const data = event.data as { state?: Record<string, unknown> }
            setMessages((previous) =>
              previous.map((message) =>
                message.id === assistantId ? { ...message, content: '行程生成完成，可以在右侧查看计划。' } : message,
              ),
            )
            if (data.state) {
              void fetchSessionSnapshot(threadId).then((snapshot) => {
                setTrip(mapSnapshotToTripSummary(snapshot))
                setItinerary(mapSnapshotToItinerary(snapshot))
                setExpensesByCategory(mapSnapshotToExpenses(snapshot))
              })
            }
          }
          if (event.event === 'error') {
            const data = event.data as { message?: string }
            setMessages((previous) =>
              previous.map((message) =>
                message.id === assistantId ? { ...message, content: data.message || '生成失败，请稍后重试。' } : message,
              ),
            )
          }
        },
      )
    } catch (error) {
      setMessages((previous) =>
        previous.map((message) =>
          message.id === assistantId
            ? { ...message, content: error instanceof Error ? error.message : '生成失败，请稍后重试。' }
            : message,
        ),
      )
    } finally {
      setIsStreaming(false)
    }
  }

  return {
    activeConversation,
    activeConversationId,
    activeDate,
    colors,
    conversations,
    currentItems,
    datesList,
    draft,
    expensesByCategory,
    isNewTripMode,
    isStreaming,
    messages,
    pieConicGradient,
    remaining,
    selectedDateIndex,
    selectConversation,
    setDraft,
    setSelectedDateIndex,
    setSiderCollapsed,
    setStructuredPreferences,
    sendMessage,
    startNewTrip,
    siderCollapsed,
    structuredPreferences,
    trip,
  }
}

export type ChatPageState = ReturnType<typeof useChatPageState>
```

- [ ] **Step 4: Disable send button while streaming**

Modify `frontend/src/components/chat/ChatInput.tsx` props:

```typescript
type ChatInputProps = {
  accentColor: string
  draft: string
  isStreaming: boolean
  onDraftChange: (value: string) => void
  onSend: () => void
  onStructuredPreferencesChange: (preferences: StructuredPreferences | undefined) => void
  structuredPreferences: StructuredPreferences | undefined
}
```

Use `disabled={isStreaming || !draft.trim()}` on the send button. Pass `isStreaming` from `ChatLayout` to `ChatInput`.

- [ ] **Step 5: Run chat tests and frontend build**

Run:

```bash
cd frontend
npm test -- src/api/__tests__/chat.test.ts
npm run build
```

Expected: both commands PASS.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add frontend/src/api/chatRequest.ts frontend/src/api/__tests__/chat.test.ts frontend/src/hooks/useChatPageState.ts frontend/src/layouts/ChatLayout.tsx frontend/src/components/chat/ChatInput.tsx
git commit -m "feat: stream chat from backend"
```

---

### Task 7: Remove Frontend Mock Data Imports and Verify End to End

**Files:**
- Modify or delete: `frontend/src/assets/profile/profileData.ts`
- Modify or delete: `frontend/src/store/historyData.ts`
- Modify or delete: `frontend/src/store/chatStore.ts`
- Check: all frontend files under `frontend/src`

- [ ] **Step 1: Search for remaining mock data imports**

Run:

```bash
rg -n "profileData|historyData|chatStore|initialMessages|assistantReplyContent|travelHistories|conversations|itineraryImagePrompts" frontend/src
```

Expected: no results for active imports. References inside files being deleted are acceptable only before deletion.

- [ ] **Step 2: Delete unused mock data files after imports are gone**

Delete these files only after Step 1 shows no active imports:

```bash
git rm frontend/src/assets/profile/profileData.ts frontend/src/store/historyData.ts frontend/src/store/chatStore.ts
```

Keep `frontend/src/assets/history/historyImages.ts` and `frontend/src/assets/chatImagePrompts.ts` only if another non-mock utility still imports them. Remove them too if `rg` shows no imports.

- [ ] **Step 3: Run backend tests**

Run:

```bash
cd backend
python -m pytest
```

Expected: PASS. If unrelated existing tests fail, record exact failing test names before changing code.

- [ ] **Step 4: Run frontend tests**

Run:

```bash
cd frontend
npm test
```

Expected: PASS.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 6: Run frontend lint**

Run:

```bash
cd frontend
npm run lint
```

Expected: PASS. If existing unrelated lint errors appear, list them with file paths and do not hide them.

- [ ] **Step 7: Final status check**

Run:

```bash
git status --short
```

Expected: only files changed by this plan appear.

- [ ] **Step 8: Commit Task 7**

Run:

```bash
git add frontend/src frontend/package.json frontend/package-lock.json
git commit -m "chore: remove frontend mock data"
```

---

## Self-Review

- Spec coverage:
  - Backend profile endpoint is covered by Task 1.
  - `api说明书/用户信息.md` is covered by Task 2.
  - Frontend API client, wrappers, SSE parsing, and mapping are covered by Task 3.
  - Profile and preferences are covered by Task 4.
  - History sessions and snapshots are covered by Task 5.
  - Chat streaming is covered by Task 6.
  - Mock removal and full verification are covered by Task 7.
- Completeness scan:
  - The plan contains no unfinished markers.
  - All tasks name exact files and commands.
- Type consistency:
  - Backend profile wire fields use snake case.
  - Frontend UI profile fields use camel case through `mapProfile`.
  - Session and snapshot mapper outputs match existing `Conversation`, `TravelHistory`, `TripSummary`, `ItineraryItem`, and `ExpenseCategory` shapes.
