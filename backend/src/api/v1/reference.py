import json
from typing import Any
from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from src.core.exceptions import AppException
from src.graph.reference_validator import reference_validator_node
from src.models.common import ApiResponse
from src.models.reference import AdoptReferenceRequest
from src.services.reference_adapter import adapt_reference_trip
from src.services.reference_trip_service import get_reference_trip, increment_reference_usage, list_reference_trips

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
    async def stream():
        try:
            draft, log = await adapt_reference_trip(reference, duration=request.duration, start_date=request.start_date, travelers=request.travelers)
            state = {**draft, "thread_id": request.thread_id, "user_id": user_id, "destination": reference["destination"], "duration": request.duration, "structured_preferences": request.structured_preferences or {}, "is_finished": False, "terminal_status": "running"}
            yield _sse("adaptation", {"reference_id": reference_id, "entries": log})
            result = await reference_validator_node(state)
            final = {**state, **result}
            yield _sse("node", {"thread_id": request.thread_id, "node": "reference_validator", "data": result})
            if result["terminal_status"] == "confirmed":
                await increment_reference_usage(reference_id)
            yield _sse("done", {"values": final, "next": [], "tasks": []})
        except Exception as exc:
            yield _sse("error", {"error": str(exc)})
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
