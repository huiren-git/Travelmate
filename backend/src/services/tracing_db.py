import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict, Union

import aiosqlite
from src.config.settings import settings

logger = logging.getLogger("travelmate.services.tracing_db")

_tracing_pool: Optional[aiosqlite.Connection] = None
# 写探针使用的临时表名（自创建、自清理，不残留数据）。
_PROBE_TABLE = "_tracing_wprobe"


# 对一条连接做"真实写"探针：CREATE/INSERT/DELETE/DROP 全是真写。
# readonly 或损坏的连接会在此抛异常 → 返回 False。
# 这样能在连接建立当下就暴露"卡住的只读连接"，而不是被
# CREATE TABLE IF NOT EXISTS / commit 的 no-op 掩盖到首条业务写才炸。
async def _probe_write(conn: aiosqlite.Connection) -> bool:
    try:
        await conn.execute(f"CREATE TABLE IF NOT EXISTS {_PROBE_TABLE}(id INTEGER PRIMARY KEY)")
        await conn.execute(f"INSERT OR REPLACE INTO {_PROBE_TABLE}(id) VALUES(1)")
        await conn.execute(f"DELETE FROM {_PROBE_TABLE}")
        await conn.execute(f"DROP TABLE {_PROBE_TABLE}")
        return True
    except Exception as exc:
        logger.warning(f"tracing 连接写探针失败（连接可能被毒化为只读）: {exc}")
        # 探针失败时尽量清理残留表；连接此刻可能 readonly，忽略清理错误。
        try:
            await conn.execute(f"DROP TABLE IF EXISTS {_PROBE_TABLE}")
        except Exception:
            pass
        return False


# 新建并初始化一条 tracing 连接（WAL + 建表）。
async def _open_tracing_conn() -> aiosqlite.Connection:
    db_path = Path(settings.tracing_database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path), isolation_level=None)
    await conn.execute("PRAGMA journal_mode = WAL")
    await _init_tracing_tables(conn)
    logger.info(f"SQLite (tracing) 连接已建立: {db_path}")
    return conn


# 关闭并清空全局连接（重连前清理用）。
async def _close_tracing_conn() -> None:
    global _tracing_pool
    if _tracing_pool is not None:
        try:
            await _tracing_pool.close()
        except Exception as exc:
            logger.warning(f"关闭旧 tracing 连接失败: {exc}")
        _tracing_pool = None


# 获取可写的 tracing 连接。
# 首次建立时做写探针；探针失败（连接被毒化为只读）则关掉重建，最多重试 3 次。
# 杜绝"一条在坏时刻打开的卡住连接被永久复用"。
async def _get_tracing_conn() -> aiosqlite.Connection:
    global _tracing_pool
    if _tracing_pool is not None:
        return _tracing_pool
    for attempt in range(1, 4):
        conn = await _open_tracing_conn()
        if await _probe_write(conn):
            _tracing_pool = conn
            return _tracing_pool
        # 探针失败：连接被毒化，关掉重建。
        try:
            await conn.close()
        except Exception:
            pass
        logger.warning(f"tracing 连接写探针失败，重建中...（尝试 {attempt}/3）")
    raise RuntimeError("tracing 连接连续 3 次写探针失败，无法获取可写连接（请重启后端并检查 tracing.db 的 -wal/-shm 是否被锁）")


async def _init_tracing_tables(conn: aiosqlite.Connection) -> None:
    """建 traces / spans / llm_events 三张表（从 db_client._init_tables 迁移）"""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            input_message TEXT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'running',
            total_tokens INTEGER DEFAULT 0,
            error_message TEXT
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_thread ON traces(thread_id)")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_span_id TEXT,
            node_name TEXT NOT NULL,
            span_type TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_ms INTEGER,
            status TEXT DEFAULT 'running',
            output_snapshot TEXT,
            error_stack TEXT
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id)")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            request_time TIMESTAMP NOT NULL,
            response_time TIMESTAMP,
            duration_ms INTEGER,
            prompt_text TEXT,
            response_text TEXT,
            prompt_tokens INTEGER,
            response_tokens INTEGER,
            total_tokens INTEGER,
            status TEXT DEFAULT 'success',
            error TEXT
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_trace ON llm_events(trace_id)")
    await conn.commit()


async def _execute_once(
    sql: str,
    params: Union[tuple, list, None] = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
):
    """单次执行：不包含重连逻辑，假定连接可用。"""
    conn = await _get_tracing_conn()
    async with conn.execute(sql, params or []) as cur:
        if fetch_one or fetch_all:
            columns = [d[0] for d in cur.description] if cur.description else []
            if fetch_one:
                row = await cur.fetchone()
                return dict(zip(columns, row)) if row else None
            return [dict(zip(columns, r)) for r in await cur.fetchall()]
        return None


async def _execute(
    sql: str,
    params: Union[tuple, list, None] = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
):
    """与 db_client.execute_query 等价的内部实现，但落在 tracing.db。

    若执行时遇到 readonly（连接运行期被毒化为只读），自动关闭旧连接、
    重建一条（_get_tracing_conn 会重新做写探针），并重试一次。仅重连一次，
    避免死循环；非连接级错误（SQL 语法等）直接抛出。
    """
    try:
        return await _execute_once(sql, params, fetch_one, fetch_all)
    except sqlite3.OperationalError as exc:
        if "readonly" in str(exc).lower():
            logger.warning(f"tracing 写失败(readonly)，关旧连接重连重试一次: {exc}")
            await _close_tracing_conn()
            return await _execute_once(sql, params, fetch_one, fetch_all)
        raise


# ============================================================
# 工具函数
# ============================================================

def _now_utc() -> str:
    """返回 ISO 格式的 UTC 时间字符串"""
    return datetime.now(timezone.utc).isoformat()


def _safe_truncate(text: Optional[str], max_len: int = 5000) -> Optional[str]:
    """截断过长的文本，防止撑爆数据库"""
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... [truncated {len(text) - max_len} chars]"


# ============================================================
# 1. Trace 生命周期管理
# ============================================================

async def start_trace(
    trace_id: str,
    thread_id: str,
    user_id: str,
    input_message: str,
) -> None:
    """
    在 API 入口处调用，初始化一条 Trace 记录。
    状态默认为 'running'，end_time 留空。
    """
    sql = """
        INSERT INTO traces (
            trace_id, thread_id, user_id, input_message,
            start_time, status, total_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        trace_id,
        thread_id,
        user_id,
        _safe_truncate(input_message, 500),
        _now_utc(),
        "running",
        0,
    )
    await _execute(sql, params)
    logger.debug(f"Trace 已开始: {trace_id}")


async def end_trace(
    trace_id: str,
    status: str,  # "success" | "error"
    error_msg: Optional[str] = None,
) -> None:
    """
    在 SSE 流结束或异常时调用，更新 Trace 状态。
    同时通过子查询累加 total_tokens（从 llm_events 表汇总）。
    """
    sql = """
        UPDATE traces
        SET
            end_time = ?,
            status = ?,
            error_message = ?,
            total_tokens = (
                SELECT COALESCE(SUM(total_tokens), 0)
                FROM llm_events
                WHERE trace_id = ?
            )
        WHERE trace_id = ?
    """
    params = (_now_utc(), status, error_msg, trace_id, trace_id)
    await _execute(sql, params)
    logger.info(f"Trace 已结束: {trace_id} -> {status}")


# ============================================================
# 2. Span 生命周期管理（由 @trace_span 装饰器调用）
# ============================================================

async def insert_span_start(
    trace_id: str,
    span_id: str,
    node_name: str,
    parent_span_id: Optional[str],
    span_type: str,  # "llm" / "io" / "function" / "workflow"
    start_time: str,
) -> None:
    """
    插入一条新的 Span 记录，状态为 'running'。
    """
    sql = """
        INSERT INTO spans (
            span_id, trace_id, parent_span_id, node_name, span_type,
            start_time, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        span_id,
        trace_id,
        parent_span_id,
        node_name,
        span_type,
        start_time,
        "running",
    )
    await _execute(sql, params)
    logger.debug(f"Span 已开始: {span_id} -> {node_name}")


async def update_span_end(
    span_id: str,
    end_time: str,
    duration_ms: float,
    status: str,  # "success" | "error"
    output: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """
    更新 Span 的结束信息。
    output 会被自动截断并序列化为 JSON 字符串。
    """
    output_snapshot = None
    if output is not None:
        try:
            # 如果是 Pydantic 模型，先转 dict；否则直接转 JSON
            if hasattr(output, "model_dump"):
                output_dict = output.model_dump()
            elif hasattr(output, "dict"):
                output_dict = output.dict()
            else:
                output_dict = output
            output_snapshot = _safe_truncate(
                json.dumps(output_dict, ensure_ascii=False, default=str),
                3000
            )
        except Exception as e:
            logger.warning(f"序列化 Span output 失败: {e}")
            output_snapshot = str(output)[:500]

    sql = """
        UPDATE spans
        SET
            end_time = ?,
            duration_ms = ?,
            status = ?,
            output_snapshot = ?,
            error_stack = ?
        WHERE span_id = ?
    """
    duration_ms_int = int(round(duration_ms))
    params = (
        end_time,
        duration_ms_int,
        status,
        output_snapshot,
        error,
        span_id,
    )
    await _execute(sql, params)
    logger.debug(f"Span 已结束: {span_id} -> {status} (耗时 {duration_ms:.1f}ms)")


# ============================================================
# 3. LLM 事件记录（由 log_llm_event 调用）
# ============================================================

async def insert_llm_event(
    trace_id: str,
    span_id: str,
    model_name: str,
    request_time: str,
    duration_ms: int,
    prompt_text: str,
    response_text: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    response_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    status: str = "success",
    error: Optional[str] = None,
) -> None:
    """
    插入一条 LLM 调用明细记录。
    自动截断过长的 Prompt 和 Response，防止数据库膨胀。
    """
    sql = """
        INSERT INTO llm_events (
            trace_id, span_id, model_name,
            request_time, response_time, duration_ms,
            prompt_text, response_text,
            prompt_tokens, response_tokens, total_tokens,
            status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    duration_ms_int = int(round(duration_ms))
    params = (
        trace_id,
        span_id,
        model_name,
        request_time,
        _now_utc(),
        duration_ms_int,
        _safe_truncate(prompt_text, 10000),    # Prompt 可能很长，截断到 10KB
        _safe_truncate(response_text, 20000),  # Response 可能更长（如行程 JSON）
        prompt_tokens,
        response_tokens,
        total_tokens,
        status,
        error,
    )
    await _execute(sql, params)
    
    #  自动累加 Token 到 traces 表
    if total_tokens and total_tokens > 0:
        await _add_tokens_to_trace(trace_id, total_tokens)
    
    logger.debug(f"LLM 事件已记录: {trace_id} -> {span_id} ({model_name}, {total_tokens} tokens)")


async def _add_tokens_to_trace(trace_id: str, delta_tokens: int) -> None:
    """
    增量累加 traces 表的 total_tokens 字段。
    使用原子操作防止并发竞态。
    """
    sql = """
        UPDATE traces
        SET total_tokens = total_tokens + ?
        WHERE trace_id = ?
    """
    await _execute(sql, (delta_tokens, trace_id))


# ============================================================
# 4. 辅助查询（供调试和 API 使用）
# ============================================================

async def get_trace_by_id(trace_id: str) -> Optional[Dict[str, Any]]:
    """查询单条 Trace 的元数据（不含 Spans 和 LLM Events）"""
    sql = "SELECT * FROM traces WHERE trace_id = ?"
    return await _execute(sql, (trace_id,), fetch_one=True)


async def get_spans_by_trace(trace_id: str) -> list:
    """查询某 Trace 下的所有 Spans（按开始时间排序）"""
    sql = """
        SELECT * FROM spans
        WHERE trace_id = ?
        ORDER BY start_time ASC
    """
    return await _execute(sql, (trace_id,), fetch_all=True)


async def get_llm_events_by_trace(trace_id: str) -> list:
    """查询某 Trace 下的所有 LLM 事件（按请求时间排序）"""
    sql = """
        SELECT * FROM llm_events
        WHERE trace_id = ?
        ORDER BY request_time ASC
    """
    return await _execute(sql, (trace_id,), fetch_all=True)


async def count_llm_events_by_trace(trace_id: str) -> int:
    """统计某 Trace 下的 LLM 调用次数。"""
    rows = await _execute(
        "SELECT COUNT(*) AS cnt FROM llm_events WHERE trace_id = ?",
        (trace_id,),
        fetch_all=True,
    )
    return int(rows[0]["cnt"]) if rows else 0


async def fetch_traces(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Dict[str, Any]], int]:
    """
    分页查询 traces 列表，按 start_time 倒序返回。

    每行聚合该 Trace 的 span_count（子查询计数）。
    时间筛选落在 start_time 上（包含边界）。
    返回 (rows, total)。
    """
    where: list[str] = []
    params: list[Any] = []
    if start_time:
        where.append("start_time >= ?")
        params.append(start_time)
    if end_time:
        where.append("start_time <= ?")
        params.append(end_time)
    if thread_id:
        where.append("thread_id = ?")
        params.append(thread_id)
    if user_id:
        where.append("user_id = ?")
        params.append(user_id)
    if status:
        where.append("status = ?")
        params.append(status)
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    count_rows = await _execute(
        f"SELECT COUNT(*) AS cnt FROM traces {where_clause}",
        params,
        fetch_all=True,
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0

    offset = (page - 1) * limit
    data_sql = f"""
        SELECT
            trace_id, thread_id, user_id, input_message,
            start_time, end_time, status, total_tokens, error_message,
            (SELECT COUNT(*) FROM spans s WHERE s.trace_id = traces.trace_id) AS span_count
        FROM traces
        {where_clause}
        ORDER BY start_time DESC
        LIMIT ? OFFSET ?
    """
    rows = await _execute(
        data_sql,
        params + [limit, offset],
        fetch_all=True,
    )
    return rows, total