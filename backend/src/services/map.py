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


async def fetch_poi_detail(city: str, name: str) -> Optional[Dict[str, Any]]:
    """按城市和名称查询高德 POI，并返回行程展示和定价需要的字段。"""
    city_text, name_text = str(city or "").strip(), str(name or "").strip()
    if not city_text or not name_text or not settings.amap_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://restapi.amap.com/v3/place/text",
                params={
                    "keywords": name_text,
                    "city": city_text,
                    "citylimit": "true",
                    "offset": 10,
                    "page": 1,
                    "extensions": "all",
                    "key": settings.amap_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
        if data.get("status") != "1":
            return None
        pois = data.get("pois") or []
        poi = next((item for item in pois if item.get("name") == name_text), pois[0] if pois else None)
        if not isinstance(poi, dict):
            return None
        return {
            "name": poi.get("name") or name_text,
            "address": poi.get("address") or "",
            "location": poi.get("location") or "",
            "price": (poi.get("biz_ext") or {}).get("cost"),
            "image_url": _first_photo_url(poi),
        }
    except Exception:
        logger.error("高德 POI 查询失败: city=%s name=%s", city_text, name_text)
        return None

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


def _as_positive_float(value: Any) -> Optional[float]:
    """将高德返回的数值字段安全转换为非负浮点数。"""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _first_present_value(*values: Any) -> Optional[float]:
    """按优先级读取高德响应中的第一个有效数值字段。"""
    for value in values:
        parsed = _as_positive_float(value)
        if parsed is not None:
            return parsed
    return None


async def amap_route_quote(
    origin: str,
    destination: str,
    mode: str,
    city: Optional[str] = None,
) -> Optional[Dict[str, float]]:
    """调用对应高德路线服务，返回距离、时长和该方式的费用（元）。"""
    if not (origin and destination and settings.amap_api_key):
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if mode in {"metro", "bus"}:
                # 公交/地铁费用来自首个换乘方案的 transit_fee 字段。
                response = await client.get(
                    "https://restapi.amap.com/v3/direction/transit/integrated",
                    params={
                        "origin": origin,
                        "destination": destination,
                        "city": city or "",
                        "extensions": "all",
                        "key": settings.amap_api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                route = payload.get("route") or {}
                transit = (route.get("transits") or [{}])[0] or {}
                distance_m = _first_present_value(transit.get("distance"), route.get("distance"))
                duration_s = _first_present_value(transit.get("duration"))
                fee = _first_present_value(transit.get("transit_fee"), transit.get("cost"))
            else:
                # 打车与网约车均使用驾车路线；网约车按道路距离乘可配置均价估算。
                response = await client.get(
                    "https://restapi.amap.com/v3/direction/driving",
                    params={
                        "origin": origin,
                        "destination": destination,
                        "strategy": 0,
                        "extensions": "all",
                        "key": settings.amap_api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                route = payload.get("route") or {}
                path = (route.get("paths") or [{}])[0] or {}
                distance_m = _first_present_value(path.get("distance"))
                duration_s = _first_present_value(path.get("duration"))
                fee = (
                    round(distance_m / 1000.0 * settings.ride_hailing_average_rate_per_km, 2)
                    if mode == "ride_hailing" and distance_m is not None
                    else _first_present_value(route.get("taxiCost"), route.get("taxi_cost"))
                )

        if payload.get("status") not in (None, "1", 1) or fee is None or distance_m is None or duration_s is None:
            return None
        return {
            "distance_km": round(distance_m / 1000.0, 2),
            "duration_minutes": max(1, round(duration_s / 60.0)),
            "cost": round(fee, 2),
        }
    except Exception:
        logger.error("高德路线费用查询失败: mode=%s origin=%s dest=%s", mode, origin, destination)
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
