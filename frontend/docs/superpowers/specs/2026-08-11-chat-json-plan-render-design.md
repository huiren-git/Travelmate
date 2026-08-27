# Chat JSON Plan Render Design

## Goal

当 `/api/v1/chat/stream` 返回结构化行程 JSON 时，前端不再把 JSON 直接显示在聊天气泡中，而是将其转换为 Travelmate 当前 UI 模型，并渲染到 ChatPage 的中间栏上方行程概览卡片和右侧行程栏。

## Scope

- 仅修改前端 ChatPage 相关类型、状态、工具函数和组件渲染。
- 新增一个后端 JSON 到前端行程模型的适配工具。
- 保留现有 Header、左侧 conversation、ChatInput、新行程空状态和聊天消息交互。
- 不修改后端接口，不改变 `/api/v1/chat/stream` 的请求方式。
- 不把后端 JSON 原文渲染到消息气泡。

## Current Context

- `useChatPageState()` 当前通过 `streamChat()` 消费 SSE。
- `streamEventContent()` 已能从 SSE 的 `messages` 中提取 AI 文本。
- `done` 事件可能携带 `state.daily_itinerary`、`state.draft_daily_itinerary`、`state.budget`、`state.draft_budget` 等结构化结果。
- `TripSummaryCard` 需要 `TripSummary`。
- `TripPlanSider` 需要 `ExpenseCategory[]`、按日期分组后的 `ItineraryItem[]`、日期索引和预算统计。
- 当前 mock 北京三日游仍作为默认旧会话数据。

## Data Model

新增前端生成行程模型：

```ts
export type GeneratedTripPlan = {
  trip: TripSummary
  itinerary: ItineraryItem[]
  expensesByCategory: ExpenseCategory[]
}
```

该模型按 conversation/thread 隔离保存：

```ts
const [generatedTripPlansByConversationId, setGeneratedTripPlansByConversationId] =
  useState<Record<string, GeneratedTripPlan>>({})
```

当前活动会话优先读取：

```ts
const generatedTripPlan = generatedTripPlansByConversationId[activeConversationId]
```

如果存在 `generatedTripPlan`，中间栏和右侧栏使用它；否则旧 mock 会话继续使用现有静态数据，新建空会话继续显示 Empty。

## Adapter

新增工具文件：

```text
src/utils/chatPlanAdapter.ts
```

职责：

- 接收任意后端 SSE data。
- 从 `data.state` 中读取结构化结果。
- 优先使用 `daily_itinerary`，其次使用 `draft_daily_itinerary`。
- 优先使用 `budget`，其次使用 `draft_budget`。
- 兼容数组、对象和常见字段命名，不因为局部字段缺失导致页面崩溃。
- 转换失败或没有行程数据时返回 `undefined`。

函数签名：

```ts
export function adaptGeneratedTripPlan(data: unknown): GeneratedTripPlan | undefined
```

### Trip Summary Mapping

`TripSummary` 字段来源：

- `title`: 优先使用 `destination + duration`，例如 `北京三日游`；否则使用 `AI 规划行程`。
- `dateRange`: 优先使用后端日期字段；缺失时显示 `待确认`。
- `people`: 优先从 `structured_preferences.travelers`、`travelers` 或可识别字段读取；缺失时默认 `1`。
- `budgetCny`: 从 budget 总额或分类合计推导；缺失时为 `0`。
- `spentCny`: 当前规划阶段默认等于预算分类合计；缺失时为 `0`。

### Itinerary Mapping

`ItineraryItem` 字段来源：

- `id`: 使用日期和索引生成稳定 id。
- `date`: 优先使用日程日期；缺失时使用 `Day N`。
- `attractionName`: 优先使用景点、地点、标题、活动名称等字段；缺失时为 `待定行程`。
- `timeRange`: 优先使用时间段、开始结束时间；缺失时为 `时间待定`。
- `priceCny`: 从费用字段读取数字；缺失时为 `0`。
- `status`: 统一为 `待确认`。
- `category`: 映射为现有 `ItineraryCategory`，无法识别时使用 `其他`。
- `imageUrl`: 使用现有 `img()` 工具生成通用旅行占位图，避免列表图片空白。

### Budget Mapping

`ExpenseCategory[]` 字段来源：

- 如果后端 budget 已有分类数组，直接映射为分类名称和金额。
- 如果 budget 是对象，读取常见 key/value 金额字段。
- 如果无法解析分类但存在总预算，生成一条 `预算` 分类。
- 分类颜色使用当前 Travelmate 色板：蓝色、珊瑚色、绿色、橙色循环分配。

## Stream Integration

`sendMessage()` 的 SSE 回调中：

1. 继续使用 `streamEventContent(event)` 更新聊天气泡文字。
2. 对每个事件调用 `adaptGeneratedTripPlan(event.data)`。
3. 如果得到 `GeneratedTripPlan`，写入：

```ts
setGeneratedTripPlansByConversationId((current) => ({
  ...current,
  [threadId]: generatedTripPlan,
}))
```

4. 同时让该 `threadId` 退出右侧 Empty 集合：

```ts
setEmptyTripPlanConversationIds((current) => {
  const next = new Set(current)
  next.delete(threadId)
  return next
})
```

5. 如果 `done` 没有行程数据，保持当前消息内容和右侧 Empty，不覆盖成固定完成文案。

## Layout Rendering

`useChatPageState()` 派生当前展示数据：

- `displayTrip = generatedTripPlan?.trip ?? trip`
- `displayExpensesByCategory = generatedTripPlan?.expensesByCategory ?? expensesByCategory`
- `displayItinerary = generatedTripPlan?.itinerary ?? itinerary`
- `displaySpentCny = displayTrip.spentCny`
- `displayRemaining = Math.max(0, displayTrip.budgetCny - displayTrip.spentCny)`

右侧栏 Empty 条件：

- 新 thread 且没有 `generatedTripPlan` 时 Empty。
- 一旦收到可适配的行程 JSON，右侧显示生成行程。

中间栏：

- 新 thread 没消息时显示 New Trip 标语。
- 新 thread 有消息但没行程时显示聊天消息，不显示旧 mock 摘要卡。
- 新 thread 收到行程后，在聊天消息上方显示生成的 `TripSummaryCard`。
- 旧 mock 会话继续显示原 `TripSummaryCard`。

## Error Handling

- JSON 适配失败时不抛出到 React 渲染层，返回 `undefined`。
- 单个日程项缺字段时使用默认文案和 `0` 金额。
- 未识别预算结构时保留 Empty 或生成最低限度预算分类，不展示原始 JSON。
- 网络错误仍按当前逻辑显示在 assistant 消息中。

## Verification

- 使用一段包含 `state.daily_itinerary` 和 `state.budget` 的样例 SSE data 验证 `adaptGeneratedTripPlan()` 能返回 `TripSummary`、`ItineraryItem[]` 和 `ExpenseCategory[]`。
- 运行 `npm run build`，确认 TypeScript 和 Vite 构建通过。
- 本地发送生成行程请求，确认聊天气泡显示 AI 文本而非大段 JSON。
- 确认中间栏上方出现生成行程概览卡片。
- 确认右侧栏从 Empty 切换为生成的预算和行程列表。
- 切换旧会话和新会话，确认各 thread 的生成行程互不串联。
