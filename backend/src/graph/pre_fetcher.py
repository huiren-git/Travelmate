"""
数据预取节点（Data Pre-fetcher）

职责：在 Agent 规划前，并发获取外部数据（天气、景点）
"""

# src/graph/pre_fetcher.py
import asyncio
import logging
from typing import Dict, Any

from src.core.tracing import trace_span
from src.graph.state import TravelAgentState
from src.utils.state_utils import get_start_date
from src.services.weather import fetch_weather_with_cache
from src.services.map import fetch_attractions_with_cache
import src.services.redis_client as redis_service

logger = logging.getLogger("travelmate.graph.pre_fetcher")

@trace_span("graph.pre_fetcher.pre_fetcher_node")
async def pre_fetcher_node(state: TravelAgentState) -> Dict[str, Any]:
    destination = state.get("destination")
    start_date = state.get("start_date")
    
    if not destination:
        logger.warning("destination 为空，跳过数据获取")
        return {}
    
    logger.info(f"获取 {destination} 的天气和景点数据")
    
    # 并发调用
    redis_client = redis_service.redis_client
    weather_task = fetch_weather_with_cache(destination, redis_client)
    attractions_task = fetch_attractions_with_cache(destination, redis_client, limit=10)
    weather_info, fetched_attractions = await asyncio.gather(weather_task, attractions_task)
    
    # 补充日期信息
    weather_info["date"] = start_date or get_start_date(state).isoformat()
    
    logger.info(f"获取到 {len(fetched_attractions)} 个景点")
    return {
        "weather_info": weather_info,
        "fetched_attractions": fetched_attractions,
    }
