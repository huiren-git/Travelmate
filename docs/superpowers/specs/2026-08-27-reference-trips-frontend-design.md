# 参考行程前端设计

## 目标

提供参考行程浏览与规则化采纳入口。用户可从 Home 或独立页面进入，选择蓝图并输入出行参数；适配过程由后端 SSE 执行，最终跳转至现有聊天页展示行程和适配日志，且不触发 LLM 规划。

## 路由与页面

新增 `/reference`，在 `AppLayout` 内渲染 `ReferenceTripsPage`。Home 主操作区的“参考行程”按钮和功能卡均跳转该路由。

页面调用 `GET /api/v1/reference/list`，采用分页卡片展示目的地、天数、评分、标签、避坑摘要和使用次数。加载态展示骨架，空态提示暂无可用方案，错误态提供重试。

## 采纳交互

每张卡片提供“使用此方案”。点击后以弹窗收集必填的出发日期、目标天数和人数，默认天数使用参考行程原始天数、人数为 2。确认后创建 `thread_id` 并调用 `POST /api/v1/reference/{id}/adopt/stream`。

页面消费 SSE：`adaptation` 保存日志，`node` 显示处理中，`error` 留在当前页并提示失败；`done` 解析最终 State 后通过 React Router state 跳转 `/chat`，携带 `threadId`、`values` 和适配日志。

## 聊天页衔接

聊天页读取一次性路由 state；将 `daily_itinerary`/`budget` 用现有 `adaptGeneratedTripPlan` 转换后注入既有面板状态，并创建或选中对应会话。聊天栏插入“已按参考方案适配”的助手消息及逐条适配日志。处理后 replace 当前 history state，避免刷新/重渲重复导入。

## 边界与测试

新增 `api/reference.ts` 复用现有 SSE 解析模式；不复制聊天的 API 代码。TypeScript 定义限制列表、采纳请求和 SSE 数据形状。使用前端构建检查类型与路由导入；重点验证 Home 跳转、列表/表单请求、SSE 完成后的聊天页接收逻辑。
