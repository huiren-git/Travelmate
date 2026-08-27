# Chat New Trip Empty State Design

## Goal

为 ChatPage 的 New Trip 按钮增加新行程空状态：点击后清空当前输入草稿和结构化偏好，中间栏显示新行程引导文案与输入框，右侧行程栏显示空状态，并保留现有会话列表与公共 Header。

## Scope

- 修改 New Trip 按钮的点击行为。
- 增加聊天页的新行程模式状态。
- 增加中间栏新行程引导空状态。
- 增加右侧行程栏空状态。
- 保留现有页面布局、颜色、输入框和发送行为。
- 不新增后端接口，不持久化新行程状态，不改现有会话数据结构。

## Current Context

- `ConversationSider` 渲染会话列表和 New Trip 按钮。
- `useChatPageState` 管理当前会话、消息、草稿、结构化偏好和行程数据。
- `ChatLayout` 组合左侧会话栏、中间聊天内容和右侧行程栏。
- `TripPlanSider` 当前始终渲染支出摘要和行程列表。
- `ChatInput` 已支持本地结构化偏好表单，并接收偏好状态与更新回调。

## Design

### State

在 `useChatPageState` 中新增 `isNewTripMode` 状态，并提供 `startNewTrip` 操作：

```ts
const [isNewTripMode, setIsNewTripMode] = useState(false)

function startNewTrip() {
  setIsNewTripMode(true)
  setDraft('')
  setStructuredPreferences(undefined)
  setSelectedDateIndex(0)
}
```

点击已有会话时退出新行程模式：

```ts
function selectConversation(conversationId: string) {
  setActiveConversationId(conversationId)
  setIsNewTripMode(false)
}
```

发送有效消息后退出新行程模式，使页面回到正常聊天视图：

```ts
if (!content) return
setIsNewTripMode(false)
```

现有 `messages`、`conversations`、行程数据和偏好消息提交逻辑保持不变。

### Component Boundaries

#### `ConversationSider`

新增 `onNewTrip` 属性，并绑定到 New Trip 按钮的 `onClick`。按钮文字和现有样式保持不变。

#### `NewTripEmptyState`

新增聊天组件，负责渲染中间栏新行程引导：

- 位于中间栏内容区域约三分之一高度处。
- 大标题：`✈️ 嘿，这次想去哪儿野`
- 小字：`告诉我你的梦中情地、出行天数，剩下的交给我来折腾。预算、路线、吃喝玩乐，全都给你安排得明明白白～`
- 不包含卡片嵌套，不遮挡底部 ChatInput。

#### `TripPlanSider`

新增 `isEmpty` 属性：

- `true` 时隐藏 `ExpenseSummaryCard` 和 `ItineraryPanel`。
- 使用 Ant Design `Empty` 的内置简单 SVG。
- 描述文字为：`开启对话一起规划行程吧`。
- `false` 时保持当前右侧栏渲染。

#### `ChatLayout`

根据 `isNewTripMode` 条件渲染中间栏：

- 新行程模式：显示 `NewTripEmptyState`，保留 `ChatInput`。
- 普通模式：显示现有 `TripSummaryCard` 和 `ChatMessages`。

同时将 `isNewTripMode` 传递给 `TripPlanSider`，并将 `startNewTrip` 传递给 `ConversationSider`。

### Interaction Flow

```text
点击 New Trip
  -> isNewTripMode = true
  -> draft = ''
  -> structuredPreferences = undefined
  -> selectedDateIndex = 0
  -> 中间栏显示标语和输入框
  -> 右侧栏显示 Empty

点击已有会话
  -> activeConversationId 更新
  -> isNewTripMode = false
  -> 恢复普通聊天布局

在新行程模式发送有效消息
  -> 保持现有消息发送逻辑
  -> isNewTripMode = false
  -> 恢复普通聊天布局
```

### Responsive and Visual Constraints

- 保持 AppHeader、左侧会话栏和中间输入框的现有结构。
- 新行程标语使用紧凑的页面级排版，不额外包裹装饰卡片。
- 中间栏内容区域使用相对定位或稳定的 flex 布局，将标语定位在可视区域上方三分之一附近。
- 右侧空状态垂直居中，避免与右栏边缘或滚动区域重叠。
- 继续使用现有 Travelmate 蓝色主色和浅灰背景，不引入新的主题色。

## Error Handling

- New Trip 操作只更新前端 React 状态，不触发网络请求。
- 空草稿仍由现有 `sendMessage` 逻辑忽略。
- New Trip 不删除会话列表或已有行程数据。

## Verification

- 运行 `npm run build`，确认 TypeScript 和 Vite 构建通过。
- 在本地 ChatPage 点击 New Trip，确认草稿与结构化偏好清空。
- 确认中间栏只显示标语和输入框。
- 确认右侧栏显示内置空 SVG 和指定文案。
- 点击已有会话，确认恢复原聊天和行程栏。
- 在新行程模式发送非空消息，确认退出空状态并显示聊天内容。
