# 参考行程后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 归档高分已完成行程，并通过 SSE 让用户无 LLM 地采纳规则适配后的参考行程。

**Architecture:** 独立 `reference.db` 保存逻辑蓝图；归档服务写入蓝图，规则适配服务构造草稿 State，轻量 LangGraph 校验后由独立 FastAPI 路由沿用现有 SSE 格式输出。

**Tech Stack:** FastAPI、Pydantic v2、aiosqlite、LangGraph、httpx、pytest。

**Spec:** `docs/superpowers/specs/2026-08-26-reference-trip-backend-design.md`

## Global Constraints

- 新建 `services/reference_db.py` 并创建 `reference.db`；不修改 `db_client.py` 来存储该表。
- 采纳中不得调用 LLM；地图/天气失败应记录日志并降级，不中断采纳。
- 仅在 `confirmed + is_finished + score >= 85` 时归档。
- 保护当前工作区已有的无关改动。

---

### Task 1: 独立数据库与参考行程服务

**Files:**
- Create: `backend/src/services/reference_db.py`
- Create: `backend/src/services/reference_trip_service.py`
- Create: `backend/tests/test_reference_trip_service.py`
- Modify: `backend/src/main.py`

**Interfaces:**
- Produces: `get_reference_db_connection()`, `init_reference_tables()`, `close_reference_db_pool()`。
- Produces: `archive_reference_trip(state, source_trace_id) -> bool`, `list_reference_trips(page, page_size) -> tuple[list[dict], int]`, `get_reference_trip(id)`, `increment_reference_usage(id)`。

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_archives_once_at_score_85(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_db, "REFERENCE_DB_PATH", tmp_path / "reference.db")
    assert await service.archive_reference_trip(confirmed_state(score=85), "trc_1")
    assert not await service.archive_reference_trip(confirmed_state(score=85), "trc_2")
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_reference_trip_service.py -v`

Expected: FAIL because reference modules do not exist.

- [ ] **Step 3: Implement the table and service**

Create the table with source trace, destination, duration, JSON sequence/rhythm/budget/tags, tips, score, usage count and timestamp. Add `sequence_hash TEXT NOT NULL` and unique `(destination, duration, sequence_hash)`. Serialize JSON deterministically, SHA-256 the sequence, flatten active itinerary items, and deduplicate warnings/suggestions. Initialize and close the pool in lifespan.

- [ ] **Step 4: Run service tests**

Run: `pytest tests/test_reference_trip_service.py -v`

Expected: PASS for threshold, duplicate, pagination and sorting.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/reference_db.py backend/src/services/reference_trip_service.py backend/src/main.py backend/tests/test_reference_trip_service.py
git commit -m "feat: add reference trip archive storage"
```

### Task 2: Normal Validator archive hook

**Files:**
- Modify: `backend/src/graph/validator.py`
- Modify: `backend/tests/test_itinerary_agent.py`

**Interfaces:**
- Consumes: `archive_reference_trip(state, source_trace_id)` from Task 1.
- Produces: best-effort archive only after normal final confirmation.

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_validator_archives_confirmed_high_score(monkeypatch):
    calls = []
    monkeypatch.setattr(validator, "archive_reference_trip", lambda state, trace: calls.append(state))
    result = await validator.validator_node(valid_state())
    assert result["terminal_status"] == "confirmed"
    assert len(calls) == 1
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_itinerary_agent.py -k archives -v`

Expected: FAIL because no archive hook exists.

- [ ] **Step 3: Implement guarded asynchronous call**

After draft promotion and only when final status is confirmed and score >= 85, await the service in a `try/except` that logs but never changes Validator results. Pass `get_trace_id()` as source trace ID.

- [ ] **Step 4: Run regression tests**

Run: `pytest tests/test_itinerary_agent.py -k "validator or archives" -v`

Expected: PASS; rejected/low-score results never archive.

- [ ] **Step 5: Commit**

```bash
git add backend/src/graph/validator.py backend/tests/test_itinerary_agent.py
git commit -m "feat: archive high-score confirmed itineraries"
```

### Task 3: POI helpers and rule adapter

**Files:**
- Modify: `backend/src/services/map.py`
- Create: `backend/src/services/reference_adapter.py`
- Create: `backend/tests/test_reference_adapter.py`

**Interfaces:**
- Produces: `find_reference_poi(city, name)` and `find_replacement_poi(city, source, indoor)` using AMap text search.
- Produces: `adapt_reference_trip(reference, request) -> tuple[dict, list[dict]]`, returning State drafts and adaptation log.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_adapter_compresses_and_scales_budget(monkeypatch):
    monkeypatch.setattr(adapter, "find_reference_poi", fake_open_poi)
    state, log = await adapter.adapt_reference_trip(reference(days=3, total=2800), request(days=2, travelers=1))
    assert len(state["draft_daily_itinerary"]) == 2
    assert state["draft_budget"]["total"] == 1400
    assert any(entry["kind"] == "duration_compressed" for entry in log)
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_reference_adapter.py -v`

Expected: FAIL because adapter does not exist.

- [ ] **Step 3: Implement deterministic adaptation**

Compress by retaining earliest capacity-fitting items; expand with distinct, interest-compatible city POIs. Treat AMap business text containing “休息”/“关闭” as closed and replace with same-city/same-type POIs. For weather descriptions containing 暴雨 or 暴雪, prefer indoor replacements. Retain the original only with a `risk_retained` log on API/replacement failure. Scale total and numeric details by `travelers / budget.travelers`, defaulting source travelers to two. Build dated, evenly split daily drafts using rhythm and record every change. Do not import any LLM module.

- [ ] **Step 4: Run adapter tests**

Run: `pytest tests/test_reference_adapter.py -v`

Expected: PASS for compression, expansion, closure/weather replacement, fallback logs and budget scaling.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/map.py backend/src/services/reference_adapter.py backend/tests/test_reference_adapter.py
git commit -m "feat: adapt reference itinerary blueprints"
```

### Task 4: Lightweight adoption graph

**Files:**
- Modify: `backend/src/graph/state.py`
- Create: `backend/src/graph/reference_validator.py`
- Modify: `backend/src/graph/graph.py`
- Create: `backend/tests/test_reference_validator.py`

**Interfaces:**
- Adds `adaptation_log: Optional[list[dict]]` to `TravelAgentState`.
- Produces: `reference_validator_node(state)` and `get_reference_adoption_graph_async()`.

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_reference_validator_promotes_without_llm(monkeypatch):
    monkeypatch.setattr("src.agents.base.get_llm", lambda **_: pytest.fail("LLM must not run"))
    result = await reference_validator_node(valid_adaptation_state())
    assert result["is_finished"] is True
    assert result["daily_itinerary"] == valid_adaptation_state()["draft_daily_itinerary"]
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_reference_validator.py -v`

Expected: FAIL because node and graph factory do not exist.

- [ ] **Step 3: Implement the one-node graph**

Validate exact day count, ISO date sequence, non-empty activities, HH:MM time, positive parsable duration and no per-day overlaps. Pass promotes drafts and sets a deterministic confirmed report; failure sets finished/failed with errors. The graph is exactly START -> reference_validator -> END and has no LLM, interrupt or retry path.

- [ ] **Step 4: Run validator tests**

Run: `pytest tests/test_reference_validator.py -v`

Expected: PASS for promotion, overlap and malformed-duration rejection with no LLM call.

- [ ] **Step 5: Commit**

```bash
git add backend/src/graph/state.py backend/src/graph/reference_validator.py backend/src/graph/graph.py backend/tests/test_reference_validator.py
git commit -m "feat: validate adopted reference itineraries"
```

### Task 5: List and adoption SSE API

**Files:**
- Create: `backend/src/models/reference.py`
- Create: `backend/src/api/v1/reference.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/test_reference_api.py`

**Interfaces:**
- Produces: `GET /api/v1/reference/list?page=1&page_size=20`.
- Produces: `POST /api/v1/reference/{reference_id}/adopt/stream` with thread ID, ISO start date, target duration, travelers, optional destination and preferences.

- [ ] **Step 1: Write failing API tests**

```python
def test_list_is_paginated(client, monkeypatch):
    monkeypatch.setattr(reference_api, "list_reference_trips", fake_list)
    assert client.get("/api/v1/reference/list?page=1&page_size=20").status_code == 200

def test_adoption_emits_adaptation_and_done(client, monkeypatch):
    patch_adoption_dependencies(monkeypatch)
    response = client.post("/api/v1/reference/1/adopt/stream", headers={"X-User-Id": "u1"}, json=payload())
    assert "event: adaptation" in response.text and "event: done" in response.text
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_reference_api.py -v`

Expected: FAIL because route and models do not exist.

- [ ] **Step 3: Implement Pydantic models and route**

Validate page bounds (max 100), positive duration/travelers and required ISO date. Return 404 for an unknown reference, 422 for destination mismatch/input, 409 for an active thread and existing ownership errors. Reuse chat serialization/tracing/run semantics without creating circular imports; emit `adaptation` before graph node updates, then standard `done`. Increment usage only after a confirmed final State. Register the router in main.

- [ ] **Step 4: Run API and chat tests**

Run: `pytest tests/test_reference_api.py tests/test_chat_api.py -v`

Expected: PASS for success SSE ordering, errors and no chat regression.

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/reference.py backend/src/api/v1/reference.py backend/src/main.py backend/tests/test_reference_api.py
git commit -m "feat: expose reference trip APIs"
```

### Task 6: Documentation and full verification

**Files:**
- Modify: `api说明书/行程管理.md`
- Modify: `api说明书/评估系统.md`

- [ ] **Step 1: Document exact request and SSE payloads**

Include the list query, adoption body, `adaptation` event structure, final `done` State and API/weather degradation semantics.

- [ ] **Step 2: Run complete backend verification**

Run: `pytest`

Expected: PASS with no test failures.

- [ ] **Step 3: Check diff quality**

Run: `git diff --check; git status --short`

Expected: no whitespace errors; only feature files plus the pre-existing unrelated changes.

- [ ] **Step 4: Commit documentation**

```bash
git add "api说明书/行程管理.md" "api说明书/评估系统.md"
git commit -m "docs: document reference trip APIs"
```

