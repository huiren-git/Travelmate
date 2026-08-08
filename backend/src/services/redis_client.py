# src/services/redis_client.py
from venv import logger
from redis.asyncio import Redis
from src.config.settings import settings

redis_client: Redis | None = None

# 初始化 Redis 连接池
async def init_redis():
    global redis_client
    # 连接 Redis
    try:
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            protocol=settings.redis_protocol,
        )
        # 发送 PING 验证连接是否成功
        await redis_client.ping()
        logger.info("✅ Redis 连接池初始化成功")
    # 捕获连接异常并记录错误日志
    except Exception as e:
        logger.error(f"❌ Redis 连接失败: {type(e).__name__}: {e}")
        redis_client = None
        raise   # 连接失败抛出异常阻止应用启动

# 关闭 Redis 连接池
async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis 连接池已关闭")