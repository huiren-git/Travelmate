# src/services/map.py
import logging
from typing import List, Dict, Any, Optional

import httpx
from redis.asyncio import Redis

from src.config.settings import settings
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger("travelmate.services.map")

CACHE_PREFIX = "attractions:"
CACHE_TTL = 86400  # 24小时


# 获取城市景点数据，优先读取统一 Redis 缓存，未命中时调用高德地图 API。
async def fetch_attractions_with_cache(city: str, redis: Optional[Redis] = None, limit: int = 10) -> List[Dict[str, Any]]:
    cache_key = f"{CACHE_PREFIX}{city}:{limit}"

    cached = await get_cached(cache_key)
    if isinstance(cached, list):
        logger.debug(f"景点缓存命中: {city}")
        return cached
    if cached is not None:
        logger.warning(f"景点缓存格式异常，忽略缓存并重新请求 API: {cache_key}")
    
    logger.info(f"调用高德地图API搜索景点: {city}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://restapi.amap.com/v3/place/text"
            params = {
                "keywords": "景点",
                "city": city,
                "citylimit": "true",
                "offset": limit,
                "page": 1,
                "extensions": "all",
                "key": settings.amap_api_key,
            }
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") != "1":
                logger.error(f"高德地图API返回错误: {data}")
                return []
            
            pois = data.get("pois", [])
            attractions = []
            for poi in pois[:limit]:
                biz_ext = poi.get("biz_ext", {})
                attraction = {
                    "name": poi.get("name", "未知景点"),
                    "address": poi.get("address", ""),
                    "location": poi.get("location", ""),  # "经度,纬度"
                    "rating": biz_ext.get("rating"),
                    "price": biz_ext.get("cost"),
                }
                attractions.append(attraction)
            
            await set_cached(cache_key, attractions, CACHE_TTL)
            return attractions
    except Exception as e:
        logger.error(f"获取景点失败: {e}")
        return []  # 返回空列表，不影响整体流程
