# src/services/db_client.py
import sqlite3
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional, Union

import aiosqlite

from src.config.settings import settings

logger = logging.getLogger("travelmate.services.db_client")

# 全局数据库连接池（单例）
_db_pool: Optional[aiosqlite.Connection] = None


async def get_db_connection() -> aiosqlite.Connection:
    """
    获取数据库连接（单例）。
    如果连接尚未初始化，则自动创建并初始化表结构。
    """
    global _db_pool
    if _db_pool is None:
        # 确保目录存在
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        _db_pool = await aiosqlite.connect(
            str(db_path),
            isolation_level=None,  # 开启自动提交模式，避免手动 commit
        )
        # 启用外键约束（虽然后续表设计没有外键，但保留作为通用配置）
        await _db_pool.execute("PRAGMA foreign_keys = ON")
        # 启用 WAL 模式，提升并发性能
        await _db_pool.execute("PRAGMA journal_mode = WAL")
        logger.info(f"SQLite 连接已建立: {db_path}")
    
    return _db_pool


# 注：traces / spans / llm_events 三张表的建表逻辑已迁移到
# src/services/tracing_db.py (_init_tracing_tables)，checkpoint.db 不再由本模块建表。


# ============================================================
# 执行 SQL 的核心函数
# ============================================================

async def execute_query(
    sql: str,
    params: Union[tuple, list, None] = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
) -> Union[None, Dict[str, Any], List[Dict[str, Any]]]:
    """
    执行 SQL 语句，并返回结果（如果需要）。
    
    Args:
        sql: SQL 语句（支持 ? 占位符）
        params: 参数（元组或列表）
        fetch_one: 是否返回单行（dict）
        fetch_all: 是否返回所有行（list of dict）
    
    Returns:
        - fetch_one=True: 返回 Dict 或 None
        - fetch_all=True: 返回 List[Dict]
        - 否则返回 None（执行 INSERT/UPDATE/DELETE）
    
    使用示例:
        # 插入一条记录（无返回值）
        await execute_query(
            "INSERT INTO traces (...) VALUES (?, ?)",
            ("trace_xxx", "thread_xxx")
        )
        
        # 查询单条记录
        row = await execute_query(
            "SELECT * FROM traces WHERE trace_id = ?",
            ("trace_xxx",),
            fetch_one=True
        )
        
        # 查询多条记录
        rows = await execute_query(
            "SELECT * FROM spans WHERE trace_id = ?",
            ("trace_xxx",),
            fetch_all=True
        )
    """
    conn = await get_db_connection()
    
    async with conn.execute(sql, params or []) as cursor:
        # 如果需要返回结果
        if fetch_one or fetch_all:
            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            if fetch_one:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return dict(zip(columns, row))
            
            if fetch_all:
                rows = await cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        
        # 不需要返回结果（INSERT / UPDATE / DELETE）
        return None


# ============================================================
# 关闭连接（在应用退出时调用）
# ============================================================

async def close_db_pool() -> None:
    """关闭全局数据库连接，在 FastAPI 的 shutdown 事件中调用"""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("SQLite 连接已关闭")