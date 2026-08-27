# MEMORY.md — travelmate/backend 长期项目笔记

## 追踪/可观测性层（traces/spans/llm_events）
- 现状（2026-08-17 改后）：`src/services/tracing_db.py` 已实现 `start_trace/end_trace/insert_span_start/update_span_end/insert_llm_event`，真实写入 traces/spans/llm_events。
- **库分离（2026-08-17 完成）**：tracing 三表已**从 checkpoint.db 分离到独立库 `data/tracing.db`**。`tracing_db.py` 自建 `_tracing_pool` 连接（`_get_tracing_conn`），指向 `settings.tracing_database_path`（`database_dir/tracing_database_filename`，默认 `./data/tracing.db`）；`_init_tracing_tables` 在该连接上建三表；原 `db_client._init_tables` 已删除，checkpoint.db 仅留给 LangGraph checkpointer。三表 DDL 完全一致。运行时已验证新写入落在 tracing.db，checkpoint.db 不再增长 tracing 数据（旧 6 行是分离前残留）。
- `chat.py` 已取消注释 `start_trace`（line ~360），`end_trace` 在正常/异常/取消路径调用；`call_llm` 经 `asyncio.create_task(insert_llm_event(...))` 写 llm_events；`tracing.py` 改为 `from src.services.tracing_db import insert_span_start, update_span_end` 转发 span 写入。
- ⚠️ 循环导入 bug（致命）：`tracing.py:10` 与 `tracing_db.py:8`(`from src.core.tracing import get_trace_id`) 互相引用，且 get_trace_id 在 tracing_db 中未被使用（死导入）。导致 tracing/tracing_db/chat/llm_utils 全部 import 失败，/chat/stream 不可达、三表均不落库。
- 最小修复：删除 `tracing_db.py:8` 的 `from src.core.tracing import get_trace_id`（已用 in-memory 验证可解循环）。修复后单次 /chat/stream：traces 写 1 行、spans/llm_events 各写多条。
- 注意：DeepSeek 经 LangChain 的 token 用量可能在 response.usage 而非 usage_metadata，可能致 token 字段为 NULL；llm_events 为火忘式 create_task 写入。

## trace_span 装饰器误用（2026-08-17 发现）
- `@trace_span`（`src/core/tracing.py:317`）的 wrapper 是 `async def`、内部 `await func(...)`，仅适用于 async 函数；套在同步 `def` 上并以同步方式调用时，返回的是协程（未 await），协程会泄露进业务数据。
- 被误装饰的同步函数共两处：`itinerary_agent.py:534` 的 `_normalize_item`（plan 模式，协程进 `day["items"]`，经 `_ensure_itinerary_image_urls` 的 `isinstance` 跳过而幸存，最终在 `validator.py:121` `item.get` → AttributeError 'coroutine' object has no attribute 'get'）；`itinerary_agent.py:639` 的 `_merge_replan_itinerary`（replan 模式，被 line 753 无 await 调用 → itinerary 成协程 → `_ensure_itinerary_image_urls` 中 `for day in itinerary` → TypeError 'coroutine' object is not iterable）。
- 修复方向：A) 让 trace_span 按 iscoroutinefunction 分流支持 sync；B) 直接删这两处 @trace_span；C) 把两函数改 async 并补 await（较侵入，不推荐）。其余被装饰函数均为 async，正确。
