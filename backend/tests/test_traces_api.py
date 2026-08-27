"""评估系统 /api/v1/traces 接口测试。"""

from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio

import src.services.tracing_db as tracing_db
from src.config.settings import settings
from src.main import app


def _iso(ts: str) -> str:
    """把 'YYYY-MM-DDTHH:MM:SS' 转成带时区的 ISO 字符串，落库格式与生产一致。"""
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).isoformat()


def _make_client() -> httpx.AsyncClient:
    # ASGITransport 不触发 lifespan，避免初始化 graph/redis/chromadb。
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def seeded_db(tmp_path, monkeypatch):
    """把 tracing 库指向临时目录，并写入 2 条 trace + spans + llm_event 样本。"""
    monkeypatch.setattr(settings, "database_dir", str(tmp_path))
    monkeypatch.setattr(tracing_db, "_tracing_pool", None)

    await tracing_db._execute(
        """INSERT INTO traces
           (trace_id, thread_id, user_id, input_message, start_time, end_time, status, total_tokens, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("trc_1", "thr_1", "user_1", "msg1",
         _iso("2026-08-17T10:00:00"), _iso("2026-08-17T10:00:08"), "success", 2000, None),
    )
    await tracing_db._execute(
        """INSERT INTO traces
           (trace_id, thread_id, user_id, input_message, start_time, end_time, status, total_tokens, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("trc_2", "thr_2", "user_2", "msg2",
         _iso("2026-08-17T11:00:00"), _iso("2026-08-17T11:00:05"), "error", 0, "boom"),
    )

    await tracing_db._execute(
        """INSERT INTO spans
           (span_id, trace_id, parent_span_id, node_name, span_type, start_time, end_time, duration_ms, status, output_snapshot, error_stack)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("spn_1", "trc_1", None, "supervisor", "function",
         _iso("2026-08-17T10:00:00"), _iso("2026-08-17T10:00:01"), 1000, "success", '{"ok":1}', None),
    )
    await tracing_db._execute(
        """INSERT INTO spans
           (span_id, trace_id, parent_span_id, node_name, span_type, start_time, end_time, duration_ms, status, output_snapshot, error_stack)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("spn_2", "trc_1", "spn_1", "itinerary_agent", "llm",
         _iso("2026-08-17T10:00:00.500"), _iso("2026-08-17T10:00:06.000"), 5500, "success", '{"days":3}', None),
    )

    await tracing_db._execute(
        """INSERT INTO llm_events
           (trace_id, span_id, model_name, request_time, response_time, duration_ms,
            prompt_text, response_text, prompt_tokens, response_tokens, total_tokens, status, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("trc_1", "spn_2", "deepseek-chat",
         _iso("2026-08-17T10:00:00.510"), _iso("2026-08-17T10:00:06.000"), 5490,
         "[System] ...", '{"x":1}', 100, 80, 180, "success", None),
    )

    await tracing_db._execute(
        """INSERT INTO spans
           (span_id, trace_id, parent_span_id, node_name, span_type, start_time, end_time, duration_ms, status, output_snapshot, error_stack)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("spn_3", "trc_2", None, "itinerary_agent", "llm",
         _iso("2026-08-17T11:00:00"), _iso("2026-08-17T11:00:02"), 2000, "error", None, "stack"),
    )

    yield

    pool = tracing_db._tracing_pool
    if pool is not None:
        await pool.close()
        tracing_db._tracing_pool = None


# 列表默认按开始时间倒序返回，聚合 span_count 并计算耗时。
@pytest.mark.asyncio
async def test_list_traces_default(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["limit"] == 20
    assert data["total_pages"] == 1
    assert [t["trace_id"] for t in data["traces"]] == ["trc_2", "trc_1"]

    by_id = {t["trace_id"]: t for t in data["traces"]}
    assert by_id["trc_1"]["span_count"] == 2
    assert by_id["trc_2"]["span_count"] == 1
    assert by_id["trc_1"]["duration_seconds"] == 8.0
    assert by_id["trc_2"]["duration_seconds"] == 5.0


# status 筛选只返回匹配项。
@pytest.mark.asyncio
async def test_list_traces_filter_status(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces", params={"status": "success"})
    assert resp.status_code == 200
    assert [t["trace_id"] for t in resp.json()["data"]["traces"]] == ["trc_1"]


# user_id 精确匹配。
@pytest.mark.asyncio
async def test_list_traces_filter_user(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces", params={"user_id": "user_2"})
    assert resp.status_code == 200
    assert [t["trace_id"] for t in resp.json()["data"]["traces"]] == ["trc_2"]


# 分页：limit=1 时 total_pages=2，第一页为倒序首条。
@pytest.mark.asyncio
async def test_list_traces_pagination(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces", params={"page": 1, "limit": 1})
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["total_pages"] == 2
    assert len(data["traces"]) == 1
    assert data["traces"][0]["trace_id"] == "trc_2"


# 非法 status 枚举值返回 40003。
@pytest.mark.asyncio
async def test_list_traces_invalid_status(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces", params={"status": "pending"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 40003
    assert body["details"]["field"] == "status"


# 非法时间格式返回 40003。
@pytest.mark.asyncio
async def test_list_traces_invalid_time_format(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces", params={"start_time": "not-a-date"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 40003


# 摘要：总耗时为 spans 耗时之和，llm 调用次数与 token 正确。
@pytest.mark.asyncio
async def test_get_trace_summary(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces/trc_1/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trace_id"] == "trc_1"
    assert data["llm_call_count"] == 1
    assert data["total_tokens"] == 2000
    assert data["total_duration_ms"] == 6500
    assert data["status"] == "success"
    assert len(data["spans"]) == 2


# 摘要：含 error span 时整体状态为 error。
@pytest.mark.asyncio
async def test_get_trace_summary_error_status(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces/trc_2/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "error"
    assert data["llm_call_count"] == 0


# 摘要 404：trace 不存在返回 40401。
@pytest.mark.asyncio
async def test_get_trace_summary_not_found(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces/nope/summary")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 40401
    assert body["details"]["trace_id"] == "nope"


# 详情：span 树形结构 + llm_events 挂载在对应 span 下。
@pytest.mark.asyncio
async def test_get_trace_detail(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces/trc_1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trace"]["trace_id"] == "trc_1"
    assert data["trace"]["status"] == "success"

    roots = data["spans"]
    assert len(roots) == 1
    assert roots[0]["span_id"] == "spn_1"
    assert roots[0]["llm_events"] == []

    assert len(roots[0]["children"]) == 1
    child = roots[0]["children"][0]
    assert child["span_id"] == "spn_2"
    assert child["parent_span_id"] == "spn_1"
    assert len(child["llm_events"]) == 1
    assert child["llm_events"][0]["model_name"] == "deepseek-chat"
    assert child["llm_events"][0]["total_tokens"] == 180


# 详情 404。
@pytest.mark.asyncio
async def test_get_trace_detail_not_found(seeded_db):
    async with _make_client() as client:
        resp = await client.get("/api/v1/traces/nope")
    assert resp.status_code == 404
    assert resp.json()["code"] == 40401
