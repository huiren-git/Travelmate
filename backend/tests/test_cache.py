import json

import pytest

import src.services.redis_client as redis_service
from src.utils.cache import delete_cached, exists_cached, get_cached, set_cached


class FakeRedis:
    """用于缓存测试的内存版 Redis 替身。"""

    # 初始化内存存储和 ttl 记录。
    def __init__(self):
        self.store = {}
        self.ttls = {}

    # 模拟 Redis get 操作。
    async def get(self, key):
        return self.store.get(key)

    # 模拟 Redis setex 操作。
    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    # 模拟 Redis delete 操作。
    async def delete(self, key):
        existed = key in self.store
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if existed else 0

    # 模拟 Redis exists 操作。
    async def exists(self, key):
        return 1 if key in self.store else 0


# 每个测试结束后清理全局 Redis 客户端。
@pytest.fixture(autouse=True)
def clear_redis_client(monkeypatch):
    monkeypatch.setattr(redis_service, "redis_client", None)


# 验证缓存读写会动态读取启动后初始化的 Redis 客户端。
@pytest.mark.asyncio
async def test_cache_uses_dynamic_redis_client(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_service, "redis_client", fake_redis)

    value = {"city": "北京", "temp": 25.0}

    assert await set_cached("weather:北京", value, 600) is True
    assert fake_redis.ttls["weather:北京"] == 600
    assert json.loads(fake_redis.store["weather:北京"]) == value
    assert await get_cached("weather:北京") == value


# 验证删除和存在性检查会返回 Redis 操作结果。
@pytest.mark.asyncio
async def test_cache_delete_and_exists(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_service, "redis_client", fake_redis)

    await set_cached("attractions:北京:10", [{"name": "故宫"}], 86400)

    assert await exists_cached("attractions:北京:10") is True
    assert await delete_cached("attractions:北京:10") is True
    assert await exists_cached("attractions:北京:10") is False


# 验证 Redis 未初始化时缓存工具会安全降级。
@pytest.mark.asyncio
async def test_cache_degrades_when_redis_is_not_initialized():
    assert await get_cached("missing") is None
    assert await set_cached("missing", {"ok": True}, 60) is False
    assert await exists_cached("missing") is False
    assert await delete_cached("missing") is False


# 验证脏缓存不是合法 JSON 时会返回原始文本，交给业务层决定是否忽略。
@pytest.mark.asyncio
async def test_cache_returns_raw_text_for_non_json_value(monkeypatch):
    fake_redis = FakeRedis()
    fake_redis.store["bad-json"] = "not json"
    monkeypatch.setattr(redis_service, "redis_client", fake_redis)

    assert await get_cached("bad-json") == "not json"
