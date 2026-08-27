# src/api/v1/health.py
from datetime import datetime, timezone
from importlib.util import find_spec
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict

from fastapi import APIRouter

from src.config.settings import settings
from src.models.common import ApiResponse
from src.models.health import HealthData
import src.services.redis_client as redis_service

router = APIRouter()
logger = logging.getLogger("travelmate.api.health")


# 检查 Redis 客户端是否已初始化且能够响应 ping。
async def _check_redis() -> Dict[str, Any]:
    redis_client = redis_service.redis_client
    if not redis_client:
        return {
            "status": "unhealthy",
            "message": "Redis 客户端未初始化",
        }

    try:
        await redis_client.ping()
    except Exception as e:
        logger.warning("Redis 健康检查失败: %s", e)
        return {
            "status": "unhealthy",
            "message": f"Redis 连接异常: {str(e)}",
        }

    return {
        "status": "healthy",
        "message": "Redis 连接正常",
    }


# 判断当前环境是否安装了 LangGraph SQLite checkpointer 依赖。
def _sqlite_checkpointer_installed() -> bool:
    for module_name in (
        "langgraph.checkpoint.sqlite",
        "langgraph.checkpoint.sqlite.aio",
    ):
        try:
            if find_spec(module_name) is not None:
                return True
        except ModuleNotFoundError:
            continue
    return False


# 检查配置的 SQLite checkpoint 数据库是否存在且可读。
def _check_sqlite() -> Dict[str, Any]:
    db_path = Path(settings.database_path)
    result: Dict[str, Any] = {
        "status": "healthy",
        "message": "SQLite checkpoint 数据库连接正常",
        "path": str(db_path),
        "exists": db_path.exists(),
    }

    if not _sqlite_checkpointer_installed():
        result.update(
            {
                "status": "unhealthy",
                "message": "未安装 langgraph-checkpoint-sqlite，当前图会回退到内存 checkpointer",
            }
        )
        return result

    if not db_path.parent.exists():
        result.update(
            {
                "status": "unhealthy",
                "message": f"SQLite 数据库目录不存在: {db_path.parent}",
            }
        )
        return result

    if not db_path.exists():
        result.update(
            {
                "status": "unhealthy",
                "message": "SQLite 数据库文件不存在，可能尚未启用磁盘 checkpointer 或尚未写入 checkpoint",
            }
        )
        return result

    try:
        db_uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(db_uri, uri=True) as conn:
            conn.execute("SELECT 1").fetchone()
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            result["tables"] = sorted(tables)
            if "checkpoints" not in tables:
                result.update(
                    {
                        "status": "unhealthy",
                        "message": "SQLite 可连接，但没有找到 checkpoints 表",
                    }
                )
                return result

            row = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()
            result["checkpoint_count"] = int(row[0])
    except Exception as e:
        logger.warning("SQLite 健康检查失败: %s", e)
        result.update(
            {
                "status": "unhealthy",
                "message": f"SQLite 连接异常: {str(e)}",
            }
        )

    return result


# 汇总 Redis 和 SQLite 的健康状态。
def _overall_status(components: Dict[str, Dict[str, Any]]) -> str:
    return "healthy" if all(item["status"] == "healthy" for item in components.values()) else "degraded"


# 返回应用和依赖组件的健康检查结果。
@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check():
    components = {
        "redis": await _check_redis(),
        "sqlite": _check_sqlite(),
    }
    status = _overall_status(components)

    return ApiResponse(
        code=200,
        message="服务运行正常" if status == "healthy" else "部分组件异常",
        data=HealthData(
            status=status,
            service=settings.app_name,
            version=settings.app_version,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            components=components,
        ),
    )
