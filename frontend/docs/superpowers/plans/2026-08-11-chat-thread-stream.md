# Chat Thread Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete ChatPage's New Trip flow so each new trip creates its own `thread_id`, isolates messages by conversation, and submits chat messages to `/api/v1/chat/stream` with structured preferences.

**Architecture:** Keep the behavior inside the existing ChatPage state boundary. `src/hooks/useChatPageState.ts` owns conversation creation, active conversation switching, per-thread message storage, and stream lifecycle; `src/api/chat.ts` owns the request type and SSE transport. Layout components stay presentational and receive derived flags for chat empty state and right-side trip-plan empty state.

**Tech Stack:** React 19, TypeScript, Ant Design, TailwindCSS, existing Vite build pipeline.

---

### Task 1: Normalize the stream request contract

**Files:**
- Modify: `src/api/chat.ts`
- Modify: `src/hooks/useChatPageState.ts`

- [ ] **Step 1: Update the request type**

In `src/api/chat.ts`, replace the current `structured_input` request field with the backend-facing `structured_preferences` field:

```ts
export type ChatStreamRequest = {
  thread_id: string
  message: string
  current_time?: string
  structured_preferences?: StructuredPreferences
}
```

Remove `toStructuredInput()` if it is no longer used. The quick-form data should be submitted as saved, not remapped to a reduced `destination/duration/budget` shape.

- [ ] **Step 2: Update the hook import**

In `src/hooks/useChatPageState.ts`, change the API import from:

```ts
import { createChatThreadId, streamChat, toStructuredInput, type ParsedSseEvent } from '../api/chat'
```

to:

```ts
import { createChatThreadId, streamChat, type ParsedSseEvent } from '../api/chat'
```

- [ ] **Step 3: Run the build to verify the API type change**

Run:

```powershell
npm run build
```

Expected: TypeScript reaches Vite build without unused import or unknown property errors. The existing Vite chunk-size warning may remain.

### Task 2: Make New Trip create a durable isolated conversation

**Files:**
- Modify: `src/hooks/useChatPageState.ts`
- Verify: `src/components/chat/ConversationSider.tsx`

- [ ] **Step 1: Keep conversation list state as the source of sidebar conversations**

Confirm `useChatPageState()` uses:

```ts
const [conversationList, setConversationList] = useState<Conversation[]>(conversations)
```

and returns:

```ts
conversations: conversationList
```

No separate sidebar state should be created inside `ConversationSider`.

- [ ] **Step 2: Ensure New Trip creates a unique thread**

Keep `startNewTrip()` creating a fresh id:

```ts
const threadId = createChatThreadId()
```

Create the new conversation with:

```ts
const newConversation: Conversation = {
  id: threadId,
  title: 'New Trip',
  updatedAt: formatConversationUpdatedAt(),
  status: conversations[0]?.status ?? conversationList[0]?.status,
}
```

If TypeScript reports that `status` can be `undefined`, use an existing mock status value from `conversations[0].status` so the value still matches the project's string-literal type.

- [ ] **Step 3: Initialize the new thread message bucket**

In `startNewTrip()`, insert the new conversation at the top and initialize its messages:

```ts
setConversationList((current) => [newConversation, ...current])
setMessagesByConversationId((current) => ({ ...current, [threadId]: [] }))
setActiveConversationId(threadId)
setIsNewTripMode(true)
setDraft('')
setStructuredPreferences(undefined)
setSelectedDateIndex(0)
```

This keeps old messages out of the new conversation and clears the quick-form state.

- [ ] **Step 4: Keep existing conversation restore behavior**

`selectConversation(conversationId)` should set the active id and exit only the transient New Trip mode:

```ts
function selectConversation(conversationId: string) {
  setActiveConversationId(conversationId)
  setIsNewTripMode(false)
}
```

The selected conversation's messages are read from `messagesByConversationId[conversationId]`.

### Task 3: Preserve the right-side empty state for new threads

**Files:**
- Modify: `src/hooks/useChatPageState.ts`
- Modify: `src/layouts/ChatLayout.tsx`
- Verify: `src/components/itinerary/TripPlanSider.tsx`

- [ ] **Step 1: Track which conversations have no trip plan**

In `useChatPageState()`, add a set of thread ids created by New Trip:

```ts
const [emptyTripPlanConversationIds, setEmptyTripPlanConversationIds] = useState<Set<string>>(() => new Set())
```

In `startNewTrip()`, add the new `threadId`:

```ts
setEmptyTripPlanConversationIds((current) => {
  const next = new Set(current)
  next.add(threadId)
  return next
})
```

- [ ] **Step 2: Derive a stable empty-state flag**

After `messages` is derived, add:

```ts
const isTripPlanEmpty = emptyTripPlanConversationIds.has(activeConversationId)
const isActiveConversationEmpty = messages.length === 0
const showNewTripEmptyState = isTripPlanEmpty && isActiveConversationEmpty
```

Return both `isTripPlanEmpty` and `showNewTripEmptyState` from the hook.

- [ ] **Step 3: Update layout usage**

In `ChatLayout`, replace the middle-column condition:

```tsx
{isNewTripMode ? (
  <NewTripEmptyState />
) : (
  ...
)}
```

with:

```tsx
{showNewTripEmptyState ? (
  <NewTripEmptyState />
) : (
  ...
)}
```

Pass:

```tsx
isEmpty={isTripPlanEmpty}
```

to `TripPlanSider`.

This keeps the right panel empty even after the first message in a new thread has been sent.

### Task 4: Submit messages to the stream endpoint safely

**Files:**
- Modify: `src/hooks/useChatPageState.ts`

- [ ] **Step 1: Snapshot state at send time**

At the top of `sendMessage()`, after validating the draft and streaming flag, capture immutable values:

```ts
const content = draft.trim()
if (!content || isStreaming) return

const threadId = activeConversationId
const preferencesSnapshot = structuredPreferences
const assistantId = `m-a-${Date.now()}`
```

Use `threadId` for every message write and stream update in this send cycle.

- [ ] **Step 2: Append optimistic messages to the fixed thread**

Append the user message and assistant placeholder to:

```ts
[threadId]: [
  ...(current[threadId] ?? []),
  nextUser,
  {
    id: assistantId,
    role: 'assistant',
    content: '正在生成行程...',
    time: formatMessageTime(),
  },
]
```

Avoid using `activeConversationId` inside the setter body for this send cycle.

- [ ] **Step 3: Update the matching conversation**

Update only the conversation whose `id === threadId`:

```ts
setConversationList((current) =>
  current.map((conversation) =>
    conversation.id === threadId
      ? {
          ...conversation,
          title: conversation.title === 'New Trip' ? conversationTitleFromMessage(content) : conversation.title,
          updatedAt: formatConversationUpdatedAt(),
        }
      : conversation,
  ),
)
```

- [ ] **Step 4: Call `/api/v1/chat/stream` with the confirmed payload**

Replace the current stream request body with:

```ts
await streamChat(
  {
    thread_id: threadId,
    message: content,
    current_time: new Date().toISOString(),
    ...(preferencesSnapshot ? { structured_preferences: preferencesSnapshot } : {}),
  },
  (event) => {
    const nextContent = streamEventContent(event)
    setMessagesByConversationId((current) => ({
      ...current,
      [threadId]: (current[threadId] ?? []).map((message) =>
        message.id === assistantId ? { ...message, content: nextContent, time: formatMessageTime() } : message,
      ),
    }))
  },
)
```

- [ ] **Step 5: Route stream failures to the fixed thread**

In the `catch` block, also use `[threadId]` instead of `[activeConversationId]` when replacing the assistant placeholder with the error message.

### Task 5: Verify end-to-end behavior

**Files:**
- Verify: `src/api/chat.ts`
- Verify: `src/hooks/useChatPageState.ts`
- Verify: `src/layouts/ChatLayout.tsx`
- Verify: `src/components/chat/ConversationSider.tsx`
- Verify: `src/components/itinerary/TripPlanSider.tsx`

- [ ] **Step 1: Run production build**

Run:

```powershell
npm run build
```

Expected: exit code `0`. The existing Vite chunk-size warning may remain.

- [ ] **Step 2: Verify request fields in source**

Run:

```powershell
rg -n "structured_input|structured_preferences|thread_id|activeConversationId" src/api/chat.ts src/hooks/useChatPageState.ts
```

Expected:

- No active `structured_input` request field remains.
- `structured_preferences` appears in `ChatStreamRequest` and the `streamChat()` call.
- `thread_id` in the request uses the fixed `threadId` snapshot.
- Stream event updates write to `[threadId]`, not `[activeConversationId]`.

- [ ] **Step 3: Verify browser behavior**

Open:

```text
http://127.0.0.1:5173/chat
```

Confirm:

- Clicking `New Trip` adds a new conversation at the top of the left sidebar.
- The new conversation becomes active.
- The middle column shows the slogan while the new conversation has no messages.
- The right sidebar shows Empty for the new conversation.
- Sending a message makes that new conversation show its own user and assistant messages.
- The right sidebar remains Empty for that new conversation after sending.
- Switching to an old conversation restores its messages; switching back to the new conversation restores the new messages.

- [ ] **Step 4: Check final diff boundaries**

Run:

```powershell
git diff --check -- src/api/chat.ts src/hooks/useChatPageState.ts src/layouts/ChatLayout.tsx src/components/chat/ConversationSider.tsx src/components/itinerary/TripPlanSider.tsx
git status --short
```

Expected: no whitespace errors in the touched frontend files. Existing unrelated dirty files may remain.
