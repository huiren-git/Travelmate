# src/services/map.py
import logging
import re
from typing import List, Dict, Any, Optional

import httpx
from redis.asyncio import Redis

from src.config.settings import settings
from src.utils.cache import get_cached, set_cached

logger = logging.getLogger("travelmate.services.map")

CACHE_PREFIX = "attractions:"
CACHE_TTL = 86400  # 24小时


def _first_photo_url(poi: Dict[str, Any]) -> str:
    photos = poi.get("photos")
    if not isinstance(photos, list):
        return ""
    if not photos:
        return ""
    first_photo = photos[0]
    if not isinstance(first_photo, dict):
        return ""
    url = first_photo.get("url")
    if not isinstance(url, str):
        return ""
    return url.strip()


# 使用目的地和活动名精确查询高德，返回第一张真实 POI 照片。
from src.core.tracing import trace_span_context


async def fetch_activity_image_url(city: str, activity: str) -> str:
    async with trace_span_context(
        "获取景点图片",
        span_type="io",
    ) as span_id:

        city_text = str(city or "").strip()
        activity_text = str(activity or "").strip()

        if not city_text or not activity_text or not settings.amap_api_key:
            return ""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://restapi.amap.com/v3/place/text",
                    params={
                        "keywords": f"{city_text} {activity_text}",
                        "city": city_text,
                        "citylimit": "true",
                        "offset": 1,
                        "page": 1,
                        "extensions": "all",
                        "key": settings.amap_api_key,
                    },
                )

                response.raise_for_status()

                data = response.json()

                if data.get("status") != "1":
                    logger.error("高德地图API返回错误: %s", data)
                    return ""

                pois = data.get("pois")

                if not isinstance(pois, list) or not pois:
                    return ""

                return _first_photo_url(pois[0])

        except Exception as e:
            logger.error(
                "高德图片查询失败: city=%s activity=%s error=%s",
                city_text,
                activity_text,
                e,
            )
            return ""

# 获取城市景点数据，优先读取统一 Redis 缓存，未命中时调用高德地图 API。
async def fetch_attractions_with_cache(
    city: str,
    redis: Optional[Redis] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:

    async with trace_span_context(
        "获取景点列表",
        span_type="io",
    ) as span_id:

        cache_key = f"{CACHE_PREFIX}{city}:{limit}"

        cached = await get_cached(cache_key)

        if isinstance(cached, list):
            logger.debug("景点缓存命中: %s", city)
            return cached

        if cached is not None:
            logger.warning(
                "景点缓存格式异常，"
                "忽略缓存并重新请求 API: %s",
                cache_key,
            )

        logger.info(
            "调用高德地图API搜索景点: %s",
            city,
        )

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

                resp = await client.get(
                    url,
                    params=params,
                )

                resp.raise_for_status()

                data = resp.json()

                if data.get("status") != "1":
                    logger.error(
                        "高德地图API返回错误: %s",
                        data,
                    )
                    return []

                pois = data.get("pois", [])

                attractions = []

                for poi in pois[:limit]:
                    biz_ext = poi.get("biz_ext", {})

                    attraction = {
                        "name": poi.get(
                            "name",
                            "未知景点",
                        ),
                        "address": poi.get(
                            "address",
                            "",
                        ),
                        "location": poi.get(
                            "location",
                            "",
                        ),
                        "rating": biz_ext.get(
                            "rating"
                        ),
                        "price": biz_ext.get(
                            "cost"
                        ),
                        "image_url": _first_photo_url(
                            poi
                        ),
                    }

                    attractions.append(
                        attraction
                    )

                await set_cached(
                    cache_key,
                    attractions,
                    CACHE_TTL,
                )

                return attractions

        except Exception as e:
            logger.error(
                "获取景点失败: %s",
                e,
            )
            return []


async def geocode_city(city: str) -> Optional[tuple[float, float]]:
    """将城市名解析为和风天气使用的 (纬度, 经度)。"""
    city_text = str(city or "").strip()
    if not city_text or not settings.amap_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": city_text, "city": city_text, "key": settings.amap_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                logger.error("高德地理编码返回错误: %s", data)
                return None

            geocodes = data.get("geocodes") or []
            location = geocodes[0].get("location", "") if geocodes else ""
            longitude, latitude = (part.strip() for part in location.split(",", 1))
            return float(latitude), float(longitude)
    except (httpx.HTTPError, ValueError, AttributeError, IndexError) as exc:
        logger.error("城市地理编码失败: city=%s error=%s", city_text, exc)
        return None


# 高德驾车距离（米）→ 公里。origin/destination 均为 "lng,lat"，失败返回 None。
async def amap_distance_km(origin: str, destination: str) -> Optional[float]:
    if not (origin and destination) or not settings.amap_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://restapi.amap.com/v3/distance",
                params={
                    "origins": origin,
                    "destination": destination,
                    "type": 1,  # 1=驾车（最贴近打车/自驾费用估算）
                    "key": settings.amap_api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "1":
                logger.error("高德距离API返回错误: %s", data)
                return None
            results = data.get("results") or [{}]
            meter = int((results[0] or {}).get("distance") or 0)
            return round(meter / 1000.0, 2)
    except Exception as e:
        logger.error("高德距离查询失败: origin=%s dest=%s error=%s", origin, destination, e)
        return None


# 获取城市美食 POI，结构同 fetch_attractions_with_cache，keywords="美食"，补全餐饮单价覆盖。
async def fetch_food_pois_with_cache(
    city: str,
    redis: Optional[Redis] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    async with trace_span_context(
        "获取美食列表",
        span_type="io",
    ) as span_id:
        cache_key = f"food:{CACHE_PREFIX}{city}:{limit}"
        cached = await get_cached(cache_key)
        if isinstance(cached, list):
            return cached
        if cached is not None:
            logger.warning("美食缓存格式异常，忽略并重新请求: %s", cache_key)

        if not settings.amap_api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://restapi.amap.com/v3/place/text",
                    params={
                        "keywords": "美食",
                        "city": city,
                        "citylimit": "true",
                        "offset": limit,
                        "page": 1,
                        "extensions": "all",
                        "key": settings.amap_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") != "1":
                    logger.error("高德美食API返回错误: %s", data)
                    return []

                food_pois = []
                for poi in (data.get("pois") or [])[:limit]:
                    biz_ext = poi.get("biz_ext", {})
                    food_pois.append(
                        {
                            "name": poi.get("name", "未知餐饮"),
                            "address": poi.get("address", ""),
                            "location": poi.get("location", ""),
                            "rating": biz_ext.get("rating"),
                            "price": biz_ext.get("cost"),  # 高德美食多为 "人均XX"
                            "image_url": _first_photo_url(poi),
                        }
                    )
                await set_cached(cache_key, food_pois, CACHE_TTL)
                return food_pois
        except Exception as e:
            logger.error("获取美食失败: %s", e)
            return []
