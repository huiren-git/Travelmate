# src/services/weather.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import httpx
from redis.asyncio import Redis

from src.config.settings import settings
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger("travelmate.services.weather")

CACHE_PREFIX = "weather:"
CACHE_TTL = 600  # 10分钟


# 获取城市实时天气，优先读取统一 Redis 缓存，未命中时调用和风天气 API。
async def fetch_weather_with_cache(city: str, redis: Optional[Redis] = None) -> Dict[str, Any]:
    cache_key = f"{CACHE_PREFIX}{city}"

    cached = await get_cached(cache_key)
    if isinstance(cached, dict):
        logger.debug(f"天气缓存命中: {city}")
        return cached
    if cached is not None:
        logger.warning(f"天气缓存格式异常，忽略缓存并重新请求 API: {cache_key}")
    
    logger.info(f"调用和风天气API: {city}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://devapi.qweather.com/v7/weather/now"
            params = {"location": city, "key": settings.qweather_api_key}
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") != "200":
                raise Exception(f"Weather API error: {data.get('code')}")
            
            now = data.get("now", {})
            weather_info = {
                "city": city,
                "temp": float(now.get("temp", 0)),
                "desc": now.get("text", "未知"),
                "humidity": float(now.get("humidity", 0)),
                "wind": now.get("windDir", "") + now.get("windScale", ""),
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            
            await set_cached(cache_key, weather_info, CACHE_TTL)
            return weather_info
    except Exception as e:
        logger.error(f"获取天气失败: {e}")
        # 降级返回默认天气（避免阻塞流程）
        return {
            "city": city,
            "temp": 25,
            "desc": "未知（API调用失败）",
            "humidity": 0,
            "wind": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
