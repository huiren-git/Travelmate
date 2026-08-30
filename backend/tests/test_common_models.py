from src.models.common import ApiResponse, ErrorDetail, ErrorResponse
from src.graph.state import ItineraryItem


def test_common_response_models_share_stable_serialization_shape():
    response = ApiResponse[dict[str, int]](
        code=200,
        message="ok",
        data={"count": 1},
    )
    error = ErrorResponse(
        code=40002,
        message="请求参数校验失败",
        details=[ErrorDetail(field="body.name", error="字段不能为空")],
    )

    assert response.model_dump() == {
        "code": 200,
        "message": "ok",
        "data": {"count": 1},
    }
    assert error.model_dump(exclude_none=True) == {
        "code": 40002,
        "message": "请求参数校验失败",
        "details": [{"field": "body.name", "error": "字段不能为空"}],
    }


def test_itinerary_item_type_declares_estimate_source():
    assert "estimate_source" in ItineraryItem.__annotations__
