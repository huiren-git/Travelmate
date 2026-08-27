import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import (
    CODE_FORBIDDEN_RESOURCE,
    CODE_INTERNAL_ERROR,
    CODE_INVALID_DECISION_ACTION,
    CODE_LLM_UNAVAILABLE,
    CODE_MISSING_MODIFY_HINT,
    CODE_SESSION_NOT_FOUND,
    ERROR_HTTP_STATUS,
    ERROR_MESSAGES,
    AppException,
    raise_forbidden_resource,
    raise_invalid_decision_action,
    raise_llm_unavailable,
    raise_missing_modify_hint,
    raise_session_not_found,
    setup_exception_handlers,
)
from src.models.common import ErrorResponse


# 验证业务状态码存在默认消息和 HTTP 状态映射。
def test_error_code_constants_have_message_and_http_status():
    assert ERROR_MESSAGES[CODE_INTERNAL_ERROR] == "服务器内部错误"
    assert ERROR_HTTP_STATUS[CODE_LLM_UNAVAILABLE] == 503
    assert ERROR_HTTP_STATUS[CODE_FORBIDDEN_RESOURCE] == 403
    assert ERROR_HTTP_STATUS[CODE_MISSING_MODIFY_HINT] == 400
    assert ERROR_HTTP_STATUS[CODE_SESSION_NOT_FOUND] == 404


# 验证 LLM 不可用抛错函数会生成 50301 业务异常。
def test_raise_llm_unavailable():
    with pytest.raises(AppException) as exc_info:
        raise_llm_unavailable(details={"error": "timeout"})

    assert exc_info.value.code == CODE_LLM_UNAVAILABLE
    assert exc_info.value.status_code == 503
    assert exc_info.value.details == {"error": "timeout"}


# 验证权限错误抛错函数会生成 40301 业务异常。
def test_raise_forbidden_resource():
    with pytest.raises(AppException) as exc_info:
        raise_forbidden_resource(details={"error": "owner mismatch"})

    assert exc_info.value.code == CODE_FORBIDDEN_RESOURCE
    assert exc_info.value.status_code == 403


# 验证恢复流程相关参数错误抛错函数符合说明书状态码。
def test_raise_resume_decision_errors():
    with pytest.raises(AppException) as missing_hint:
        raise_missing_modify_hint()
    with pytest.raises(AppException) as invalid_action:
        raise_invalid_decision_action()

    assert missing_hint.value.code == CODE_MISSING_MODIFY_HINT
    assert invalid_action.value.code == CODE_INVALID_DECISION_ACTION


# 验证会话不存在抛错函数会带上 thread_id 详情。
def test_raise_session_not_found():
    with pytest.raises(AppException) as exc_info:
        raise_session_not_found(thread_id="thread_xxx")

    assert exc_info.value.code == CODE_SESSION_NOT_FOUND
    assert exc_info.value.details["thread_id"] == "thread_xxx"


# 验证 FastAPI 参数校验错误会转换成文档约定的 40002。
def test_request_validation_error_handler_uses_business_code():
    app = FastAPI()
    setup_exception_handlers(app)

    @app.get("/items/{item_id}")
    async def read_item(item_id: int):
        return {"item_id": item_id}

    response = TestClient(app).get("/items/not-int")

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 40002
    assert body["message"] == ERROR_MESSAGES[40002]


def test_app_exception_handler_returns_error_response_shape():
    app = FastAPI()
    setup_exception_handlers(app)

    @app.get("/forbidden")
    async def forbidden():
        raise AppException(
            code=CODE_FORBIDDEN_RESOURCE,
            details={"error": "owner mismatch"},
        )

    response = TestClient(app).get("/forbidden")

    assert response.status_code == 403
    assert response.json() == ErrorResponse(
        code=CODE_FORBIDDEN_RESOURCE,
        message=ERROR_MESSAGES[CODE_FORBIDDEN_RESOURCE],
        details={"error": "owner mismatch"},
    ).model_dump(exclude_none=True)
