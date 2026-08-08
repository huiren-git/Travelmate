# src/utils/cache.py
import json
import logging
from typing import Any, Optional

import src.services.redis_client as redis_service

logger = logging.getLogger("travelmate.utils.cache")


# 动态获取当前 Redis 客户端，避免启动后初始化导致的旧引用问题。
def _get_redis_client():
    return redis_service.redis_client


# 检查缓存 key 是否为非空字符串。
def _valid_key(key: str) -> bool:
    return isinstance(key, str) and bool(key.strip())


# 检查 ttl 是否为正整数。
def _valid_ttl(ttl: int) -> bool:
    return isinstance(ttl, int) and ttl > 0


# 从 Redis 获取缓存数据，并自动反序列化 JSON。
async def get_cached(key: str) -> Optional[Any]:
    """
    从 Redis 获取缓存数据，自动反序列化 JSON
    
    Args:
        key: 缓存键
    
    Returns:
        缓存的数据（Python 对象）或 None
    """
    if not _valid_key(key):
        logger.warning("缓存读取失败：key 不能为空")
        return None

    redis_client = _get_redis_client()
    if redis_client is None:
        return None
    try:
        data = await redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)
    except json.JSONDecodeError as e:
        logger.warning(f"缓存数据 JSON 解析失败 [key={key}]: {e}")
        # 可能是存储了非 JSON 格式，尝试返回原始字符串
        return data
    except Exception as e:
        logger.warning(f"缓存读取失败 [key={key}]: {type(e).__name__}: {e}")
        return None

# 将数据存入 Redis 缓存，并自动序列化为 JSON。
async def set_cached(key: str, value: Any, ttl: int) -> bool:
    """
    将数据存入 Redis 缓存，自动序列化为 JSON
    
    Args:
        key: 缓存键
        value: 要缓存的数据（可 JSON 序列化的对象）
        ttl: 过期时间（秒）
    
    Returns:
        是否成功
    """
    if not _valid_key(key):
        logger.warning("缓存写入失败：key 不能为空")
        return False
    if not _valid_ttl(ttl):
        logger.warning(f"缓存写入失败：ttl 必须为正整数 [key={key}, ttl={ttl}]")
        return False

    redis_client = _get_redis_client()
    if redis_client is None:
        return False
    try:
        # 将 value 转为 JSON 字符串
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await redis_client.setex(key, ttl, serialized)
        return True
    except TypeError as e:
        logger.error(f"缓存数据无法序列化为 JSON [key={key}]: {e}")
        return False
    except Exception as e:
        logger.warning(f"缓存写入失败 [key={key}]: {type(e).__name__}: {e}")
        return False


# 删除指定缓存 key。
async def delete_cached(key: str) -> bool:
    """删除缓存"""
    if not _valid_key(key):
        logger.warning("缓存删除失败：key 不能为空")
        return False

    redis_client = _get_redis_client()
    if redis_client is None:
        return False
    try:
        deleted = await redis_client.delete(key)
        return deleted > 0
    except Exception as e:
        logger.warning(f"缓存删除失败 [key={key}]: {type(e).__name__}: {e}")
        return False


# 检查指定缓存 key 是否存在。
async def exists_cached(key: str) -> bool:
    """检查缓存是否存在"""
    if not _valid_key(key):
        logger.warning("缓存存在性检查失败：key 不能为空")
        return False

    redis_client = _get_redis_client()
    if redis_client is None:
        return False
    try:
        return await redis_client.exists(key) > 0
    except Exception as e:
        logger.warning(f"缓存存在性检查失败 [key={key}]: {type(e).__name__}: {e}")
        return False
