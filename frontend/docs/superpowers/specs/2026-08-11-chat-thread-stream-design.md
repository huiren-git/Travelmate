# Chat Thread Stream Design

## Goal

补充改造 ChatPage 的 New Trip 和发送消息逻辑：点击 New Trip 时创建新的 conversation 和 `thread_id`，切换为当前会话，并按会话隔离消息；发送消息时提交到 `/api/v1/chat/stream`，并把快速表单中的结构化偏好随请求一起发送。

## Scope

- 仅修改前端 ChatPage 相关状态、类型、API 工具和布局交互。
- 保留现有 Header、ChatInput 视觉样式、New Trip 空状态标语和右侧空状态文案。
- 不新增后端代码，不改变页面整体布局。
- 不删除已有 mock conversation 和静态北京三日游数据。

## Current Context

- `src/api/chat.ts` 已有 `createChatThreadId()`、`streamChat()` 和 SSE 解析逻辑。
- `src/hooks/useChatPageState.ts` 已开始使用 `conversationList`、`messagesByConversationId`、`isNewTripMode` 和 `isStreaming`。
- `ConversationSider` 已有 New Trip 按钮回调入口。
- `ChatLayout` 已能根据 `isNewTripMode` 显示中间栏新行程标语，并让右侧栏显示 Empty。

## Design

### Conversation And Thread Creation

`New Trip` 每次点击都创建新的 `thread_id`：

```ts
const threadId = createChatThreadId()
```

随后插入一条新的 conversation：

```ts
{
  id: threadId,
  title: 'New Trip',
  updatedAt: formatConversationUpdatedAt(),
  status: '进行中',
}
```

同时：

- `activeConversationId = threadId`
- `messagesByConversationId[threadId] = []`
- `isNewTripMode = true`
- `draft = ''`
- `structuredPreferences = undefined`
- `selectedDateIndex = 0`

### Message Isolation

聊天消息以 `Record<string, ChatMessage[]>` 存储：

```ts
messagesByConversationId[conversationId]
```

当前中间栏只读取：

```ts
const messages = messagesByConversationId[activeConversationId] ?? []
```

这样新建会话不会复用旧消息，切换旧会话时也能恢复对应消息。

### Empty State Boundary

新增会话的空状态由当前会话自己的消息数量决定：

```ts
const isActiveConversationEmpty = messages.length === 0
```

中间栏：

- `isNewTripMode && isActiveConversationEmpty` 时显示 New Trip 标语。
- 发送第一条有效消息后显示当前会话消息列表。

右侧栏：

- 对没有行程数据的新建 `thread_id` 显示 Empty。
- 已有 mock 会话继续显示当前静态行程侧栏。

### Stream Request

`sendMessage()` 在发送开始时固定当前 `threadId`，避免用户在流式返回期间切换会话导致 assistant 消息写入错误会话：

```ts
const threadId = activeConversationId
```

请求提交到：

```text
POST /api/v1/chat/stream
```

请求体包含：

```ts
{
  thread_id: threadId,
  message: content,
  current_time: new Date().toISOString(),
  structured_preferences: structuredPreferences,
}
```

如果现有 API 工具仍保留 `structured_input`，需要统一为后端约定的 `structured_preferences` 字段，避免前端保存的快速表单数据在提交时丢失。

### Optimistic Messages And Streaming

发送时：

1. 校验 `draft.trim()`，空消息直接返回。
2. 如果正在 streaming，直接返回，避免同一输入重复提交。
3. 固定 `threadId` 和 `preferencesSnapshot`。
4. 清空输入框。
5. 向 `messagesByConversationId[threadId]` 追加用户消息。
6. 追加一个 assistant 占位消息，内容为“正在生成行程...”。
7. 调用 `streamChat()`。
8. 每个 SSE 事件更新同一个 assistant 消息。
9. 失败时将 assistant 消息替换为错误文案。
10. 请求结束后恢复 `isStreaming = false`。

发送成功发起后：

- `isNewTripMode = false`
- 新会话标题如果仍是 `New Trip`，改为用户首条消息的摘要。
- conversation 的 `updatedAt` 更新时间。

### Structured Preferences

快速表单偏好仍只保存在前端状态。发送时使用快照：

```ts
const preferencesSnapshot = structuredPreferences
```

并作为 `structured_preferences` 提交。New Trip 创建新会话时会清空该状态，避免把旧会话偏好带入新行程。

### Error Handling

- 网络错误或非 2xx 响应显示在 assistant 占位消息中。
- `streamChat()` 缺少 response body 时抛出错误，并由 `sendMessage()` 展示。
- SSE 解析失败不应中断整个 UI；若现有解析会抛错，错误会进入失败分支。
- 切换会话不取消正在进行的请求；返回内容仍写入发送时固定的 `threadId`。

## Verification

- 运行 `npm run build`，确认 TypeScript 和 Vite 构建通过。
- 点击 New Trip，确认左侧新增 conversation，当前会话切换到新 `thread_id`。
- 确认新会话中间栏为空状态，旧消息不会显示。
- 确认右侧栏对新会话显示 Empty。
- 在新会话发送消息，确认请求发往 `/api/v1/chat/stream`，请求体包含 `thread_id`、`message`、`current_time` 和 `structured_preferences`。
- 切换旧会话后确认旧消息恢复，切回新会话后确认新会话消息仍保留。
