# src/services/weather.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import httpx
from redis.asyncio import Redis

from src.config.settings import settings
from src.services.map import geocode_city
from src.utils.cache import get_cached, set_cached
from src.core.tracing import trace_span_context

logger = logging.getLogger("travelmate.services.weather")

CACHE_PREFIX = "weather:"
CACHE_TTL = 600  # 10分钟


# 获取城市实时天气，优先读取统一 Redis 缓存，未命中时调用和风天气 API。
async def fetch_weather_with_cache(city: str, redis: Optional[Redis] = None) -> Dict[str, Any]:
    cache_key = f"{CACHE_PREFIX}{city}"

    # 1. 读取缓存
    cached = await get_cached(cache_key)
    if isinstance(cached, dict):
        logger.debug(f"天气缓存命中: {city}")
        return cached
    if cached is not None:
        logger.warning(f"天气缓存格式异常，忽略缓存并重新请求 API: {cache_key}")
    
    logger.info(f"调用和风天气API: {city}")
    
    # 2. 追踪 HTTP API 调用
    try:
        async with trace_span_context("weather_api", "io") as span_id:
            coordinates = await geocode_city(city)
            if coordinates is None:
                raise ValueError(f"无法解析城市坐标: {city}")
            latitude, longitude = coordinates
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = f"https://{settings.qweather_api_host}/weather/v1/current/{latitude:.2f}/{longitude:.2f}"
                headers = {"X-QW-Api-Key": settings.qweather_api_key}
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                temperature = data.get("temperature") or {}
                condition = data.get("condition") or {}
                wind = data.get("wind") or {}
                humidity = data.get("humidity")
                if not isinstance(humidity, (int, float)):
                    raise ValueError("Weather API response does not contain humidity")
                weather_info = {
                    "city": city,
                    "temp": float(temperature.get("value", 0)),
                    "desc": condition.get("text", "未知"),
                    "humidity": float(humidity * 100),
                    "wind": f"{(wind.get('direction') or {}).get('compass', '')}{wind.get('scale', '')}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }
            
            # 3. 写入缓存（不追踪，因为是内部 I/O）
            await set_cached(cache_key, weather_info, CACHE_TTL)
            return weather_info
            
    except Exception as e:
        logger.error(f"获取天气失败: {e}")
        # 降级返回（不追踪，因为这是异常兜底）
        return {
            "city": city,
            "temp": 25,
            "desc": "未知（API调用失败）",
            "humidity": 0,
            "wind": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
