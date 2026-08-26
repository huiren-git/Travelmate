# 参考行程后端设计

## 目标与范围

实现高分已完成行程的自动归档、分页浏览和无 LLM 的规则化采纳流程。范围仅含后端 API、SQLite 持久化、LangGraph 适配分支和 SSE 输出；前端入口不在本次变更内。

## 数据模型

新建 `services/reference_db.py`，独立管理 `reference.db` 的异步 SQLite 单例连接、WAL/外键设置、关闭逻辑与建表初始化。`reference_trips` 仅创建在该独立数据库中，主业务 SQLite 和既有 `db_client.py` 不承担此表。记录保留逻辑蓝图而非原始日期：目的地、原始天数、按顺序的景点名 `sequence`、对应时长 `rhythm`、原始预算、标签、避坑经验、评分和使用次数。

`sequence_hash` 是 `sequence` 的稳定 SHA-256（UTF-8 JSON、固定分隔符、保持顺序），并与 `destination`、`duration` 组成唯一索引。它代替 SQLite 对 JSON 文本的唯一约束，避免序列化格式不同造成重复。

归档标签由现有结构化偏好的节奏/兴趣及预算等级生成；避坑经验把 Validator 报告中的 warnings 和 suggestions 归并、去空、去重为文本摘要。

## 自动归档

Validator 成功确认行程时调用归档服务。服务仅在 `is_finished` 为真、`terminal_status == "confirmed"` 且报告评分大于等于 85 时写入。它从已生效 `daily_itinerary` 展平得到序列与节奏，并用 `INSERT ... ON CONFLICT DO NOTHING` 保证幂等。

归档失败只记录日志，不影响本次行程确认或 SSE 完成事件。

## 列表 API

`GET /api/v1/reference/list?page=1&page_size=20` 返回按 `score DESC, usage_count DESC, created_at DESC` 排列的分页结果。每项含 id、destination、duration、score、tags、experience_tips 摘要、usage_count 与 created_at；不返回预算和完整蓝图。页码和大小均校验为正数，最大页大小为 100。

## 采纳 SSE API

`POST /api/v1/reference/{reference_id}/adopt/stream` 使用现有 `X-User-Id` 请求头和 SSE 响应约定。请求体：

```json
{
  "thread_id": "thread_123",
  "start_date": "2026-10-01",
  "duration": 2,
  "destination": "北京",
  "travelers": 1,
  "structured_preferences": {
    "interests": ["历史人文"],
    "pace": "relaxed"
  }
}
```

`destination` 缺省时使用参考行程目的地；显式给出的不同目的地会以 422 拒绝，因为跨城市无法保证“同区域替换”的语义。`duration`、`start_date` 和 `travelers` 必填且分别为正整数、ISO 日期和正整数。`thread_id` 复用现有会话并执行所有权检查。

接口首先加载参考行程，再由规则引擎适配，整个过程不调用 LLM：

1. 根据目标天数压缩或扩展景点序列。压缩时优先移除超出每日承载的尾部项目；扩展时从高德在目的地内找到、且与用户兴趣相符的补充 POI。每项变更写入日志。
2. 用高德 POI 文本搜索获取候选景点详情和 `business` 开放信息。无法确认当日开放或确认闭馆时，从同一行政区/商圈的同类 POI 中选择评分最高者替换；没有候选时保留原项并记录风险。
3. 读取既有天气服务。暴雨或暴雪时，将户外活动替换为同区域室内 POI；无法替换时在日志标记风险。
4. 使用 `travelers / reference_travelers` 缩放预算。参考人数从预算元数据读取，历史数据缺失时默认 2 人并明确记录日志。各预算明细与总额按同一比例缩放、保留两位小数。
5. 从序列/节奏构造 `draft_daily_itinerary`（按天平均切分，日期从 start_date 顺延）、以及 `draft_budget`；同时生成 `adaptation_log`。

适配成功后，专用 LangGraph 分支跳过 Supervisor、Pre-fetcher、Itinerary Agent、Budget Agent 和所有 LLM 调用，直接运行轻量 Validator。轻量校验只检查日期数、项目时间顺序、时长格式/重叠和基本空值；通过后将草稿提升为 `daily_itinerary`、`budget`，置 confirmed/finished。失败则产生确定性错误与日志，不进行自动重试。

API 以现有 `node` / `done` / `error` SSE 格式返回；适配过程额外发出 `adaptation` 事件，载荷为 `{"reference_id": 1, "entries": [...]}`。最终 `done` 状态中也包含 `adaptation_log`，供断线重连或仅消费最终快照的客户端读取。校验通过后递增 `usage_count`。

## 模块边界

- `services/reference_db.py`：创建/关闭 `reference.db` 连接，并初始化 `reference_trips` 表和索引。
- `services/reference_trip_service.py`：通过 `reference_db.py` 归档、分页查询、引用加载和使用次数更新。
- `services/reference_adapter.py`：纯规则适配编排、与地图/天气服务交互、日志构造和 State 草稿转换。
- `api/v1/reference.py`：列表和采纳 SSE 路由，沿用 chat API 的活动运行控制、会话所有权及 SSE 编码。
- `graph/reference_validator.py`：无 LLM 的轻量校验节点。
- `graph/graph.py`：独立的采纳图工厂，避免改动普通规划路由。
- `models/reference.py`：请求和响应 Pydantic 模型。

## 失败处理与可观测性

不存在的参考行程返回 404；正在运行的同一会话返回 409；日期、人数、天数或跨目的地输入返回 422。高德/天气暂时不可用不使采纳失败，而是降级保留景点并给出适配日志。数据库查询或图执行异常会按现有 API 规则产生 `error` SSE 事件。

## 测试

新增单元测试覆盖：评分门槛和幂等归档、列表排序/分页、天数压缩与扩展、天气/闭馆替换、预算缩放、无 LLM 轻量校验。新增 API 测试覆盖列表、采纳 SSE 的 adaptation/done 事件、错误状态和使用次数递增。所有外部地图与天气调用均通过 mock 隔离。
