import asyncio
import json
from typing import Any
from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from src.core.exceptions import AppException
from src.core.tracing import generate_trace_id, set_trace_id
from src.graph.graph import build_reference_adoption_graph, get_graph_async
from src.models.common import ApiResponse
from src.models.reference import AdoptReferenceRequest
from src.agents.cost_enrich import enrich_itinerary_costs
from src.services.reference_adapter import adapt_reference_trip, build_reference_budget
from src.services.reference_trip_service import get_reference_trip, increment_reference_usage, list_reference_trips
from src.services.travel_logistics import build_travel_logistics, enrich_local_transport_legs
from src.services.tracing_db import end_trace, start_trace

router = APIRouter(prefix="/reference")

def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

@router.get("/list")
async def reference_list(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    items, total = await list_reference_trips(page, page_size)
    summaries = [{key: item.get(key) for key in ("id", "destination", "duration", "travelers", "score", "tags", "experience_tips", "usage_count", "created_at")} for item in items]
    return ApiResponse(code=200, message="获取成功", data={"items": summaries, "total": total, "page": page, "page_size": page_size})

@router.post("/{reference_id}/adopt/stream")
async def adopt_reference(reference_id: int, request: AdoptReferenceRequest, user_id: str = Header(..., alias="X-User-Id")):
    reference = await get_reference_trip(reference_id)
    if reference is None:
        raise AppException(code=40401, message="参考行程不存在", status_code=404)
    if request.destination and request.destination != reference["destination"]:
        raise AppException(code=40002, message="目的地必须与参考行程一致", status_code=422)

    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    await start_trace(
        trace_id=trace_id,
        thread_id=request.thread_id,
        user_id=user_id,
        input_message=f"采纳参考行程：{reference['destination']}",
    )

    async def stream():
        try:
            draft, log = await adapt_reference_trip(reference, duration=request.duration, start_date=request.start_date, travelers=request.travelers)
            preferences = {**(request.structured_preferences or {}), "travelers": request.travelers}
            state = {
                **draft,
                "thread_id": request.thread_id,
                "user_id": user_id,
                "destination": reference["destination"],
                "start_date": request.start_date,
                "duration": request.duration,
                "travelers": request.travelers,
                "structured_preferences": preferences,
                "is_finished": False,
                "terminal_status": "running",
            }
            await enrich_itinerary_costs(state["draft_daily_itinerary"], state)
            logistics = build_travel_logistics(state, state["draft_daily_itinerary"])
            await enrich_local_transport_legs(logistics["local_transport_legs"])
            state["travel_logistics"] = logistics
            state["draft_budget"] = build_reference_budget(
                state["draft_daily_itinerary"],
                logistics,
                str(preferences.get("budget_level") or "mid"),
            )
            yield _sse("adaptation", {"reference_id": reference_id, "entries": log})
            main_graph = await get_graph_async()
            adoption_graph = build_reference_adoption_graph(checkpointer=main_graph.checkpointer)
            final = await adoption_graph.ainvoke(
                state,
                {"configurable": {"thread_id": request.thread_id}},
            )
            yield _sse("node", {"thread_id": request.thread_id, "node": "reference_validator", "data": final})
            if final["terminal_status"] == "confirmed":
                await increment_reference_usage(reference_id)
            await end_trace(trace_id, status="success")
            yield _sse("done", {"values": final, "next": [], "tasks": []})
        except asyncio.CancelledError:
            await end_trace(trace_id, status="cancelled")
            raise
        except Exception as exc:
            await end_trace(trace_id, status="error", error_msg=str(exc))
            yield _sse("error", {"error": str(exc)})
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
