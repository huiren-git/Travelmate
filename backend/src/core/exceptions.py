"""统一业务异常与错误码定义。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.core.logging import get_logger

logger = get_logger("exceptions")

CODE_INTERNAL_ERROR = 50001
CODE_LLM_UNAVAILABLE = 50301
CODE_DATABASE_UNAVAILABLE = 50302

CODE_MISSING_USER_ID = 40101
CODE_INVALID_TOKEN = 40102
CODE_FORBIDDEN_RESOURCE = 40301

CODE_VALIDATION_ERROR = 40002
CODE_INVALID_PARAMETER = 40003
CODE_INVALID_BUDGET_RANGE = 40004
CODE_MISSING_MODIFY_HINT = 40005
CODE_INVALID_DECISION_ACTION = 40006
CODE_MISSING_PREFERENCE_CONTENT = 40007

CODE_SESSION_NOT_FOUND = 40401
CODE_ITINERARY_SNAPSHOT_NOT_FOUND = 40402
CODE_PREFERENCE_TAG_NOT_FOUND = 40403

CODE_SESSION_NOT_INTERRUPTED = 40901

ERROR_MESSAGES: Dict[int, str] = {
    CODE_INTERNAL_ERROR: "服务器内部错误",
    CODE_LLM_UNAVAILABLE: "AI 服务暂时不可用，请稍后重试",
    CODE_DATABASE_UNAVAILABLE: "数据服务异常，请检查网络或联系管理员",
    CODE_MISSING_USER_ID: "缺少用户身份标识",
    CODE_INVALID_TOKEN: "Token 无效或已过期",
    CODE_FORBIDDEN_RESOURCE: "无权操作该资源",
    CODE_VALIDATION_ERROR: "请求参数校验失败",
    CODE_INVALID_PARAMETER: "参数类型或枚举值错误",
    CODE_INVALID_BUDGET_RANGE: "预算下限不能高于上限",
    CODE_MISSING_MODIFY_HINT: "修改操作缺少具体指令",
    CODE_INVALID_DECISION_ACTION: "决策类型无效",
    CODE_MISSING_PREFERENCE_CONTENT: "添加偏好缺少内容",
    CODE_SESSION_NOT_FOUND: "会话不存在或已过期",
    CODE_ITINERARY_SNAPSHOT_NOT_FOUND: "行程快照不存在",
    CODE_PREFERENCE_TAG_NOT_FOUND: "用户偏好标签不存在",
    CODE_SESSION_NOT_INTERRUPTED: "当前会话不在中断状态，无需恢复",
}

ERROR_HTTP_STATUS: Dict[int, int] = {
    CODE_INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    CODE_LLM_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    CODE_DATABASE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    CODE_MISSING_USER_ID: status.HTTP_401_UNAUTHORIZED,
    CODE_INVALID_TOKEN: status.HTTP_401_UNAUTHORIZED,
    CODE_FORBIDDEN_RESOURCE: status.HTTP_403_FORBIDDEN,
    CODE_VALIDATION_ERROR: status.HTTP_400_BAD_REQUEST,
    CODE_INVALID_PARAMETER: status.HTTP_400_BAD_REQUEST,
    CODE_INVALID_BUDGET_RANGE: status.HTTP_400_BAD_REQUEST,
    CODE_MISSING_MODIFY_HINT: status.HTTP_400_BAD_REQUEST,
    CODE_INVALID_DECISION_ACTION: status.HTTP_400_BAD_REQUEST,
    CODE_MISSING_PREFERENCE_CONTENT: status.HTTP_400_BAD_REQUEST,
    CODE_SESSION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    CODE_ITINERARY_SNAPSHOT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    CODE_PREFERENCE_TAG_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    CODE_SESSION_NOT_INTERRUPTED: status.HTTP_409_CONFLICT,
}


class AppException(Exception):
    """业务异常，统一携带业务码、HTTP 状态码和详情。"""

    # 初始化业务异常对象。
    def __init__(
        self,
        code: int,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Any] = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "业务异常")
        self.status_code = status_code or ERROR_HTTP_STATUS.get(code, status.HTTP_400_BAD_REQUEST)
        self.details = details


# 根据业务码创建并抛出 AppException。
def raise_app_exception(
    code: int,
    message: Optional[str] = None,
    details: Optional[Any] = None,
    status_code: Optional[int] = None,
) -> None:
    raise AppException(
        code=code,
        message=message,
        status_code=status_code,
        details=details,
    )


# 抛出未捕获的系统内部错误。
def raise_internal_error(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_INTERNAL_ERROR, message=message, details=details)


# 抛出 LLM API 不可用或超时错误。
def raise_llm_unavailable(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_LLM_UNAVAILABLE, message=message, details=details)


# 抛出数据库连接失败错误。
def raise_database_unavailable(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_DATABASE_UNAVAILABLE, message=message, details=details)


# 抛出缺少用户身份标识错误。
def raise_missing_user_id(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_MISSING_USER_ID, message=message, details=details)


# 抛出 Token 无效或已过期错误。
def raise_invalid_token(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_INVALID_TOKEN, message=message, details=details)


# 抛出无权操作资源错误。
def raise_forbidden_resource(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_FORBIDDEN_RESOURCE, message=message, details=details)


# 抛出请求参数校验失败错误。
def raise_validation_error(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_VALIDATION_ERROR, message=message, details=details)


# 抛出参数类型或枚举值错误。
def raise_invalid_parameter(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_INVALID_PARAMETER, message=message, details=details)


# 抛出预算上下限非法错误。
def raise_invalid_budget_range(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_INVALID_BUDGET_RANGE, message=message, details=details)


# 抛出修改操作缺少 hint 错误。
def raise_missing_modify_hint(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_MISSING_MODIFY_HINT, message=message, details=details)


# 抛出用户决策 action 非法错误。
def raise_invalid_decision_action(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_INVALID_DECISION_ACTION, message=message, details=details)


# 抛出添加偏好缺少 content 错误。
def raise_missing_preference_content(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_MISSING_PREFERENCE_CONTENT, message=message, details=details)


# 抛出会话不存在错误。
def raise_session_not_found(thread_id: Optional[str] = None, details: Optional[Any] = None) -> None:
    details = details or {"thread_id": thread_id, "error": "未找到该会话记录"}
    raise_app_exception(CODE_SESSION_NOT_FOUND, details=details)


# 抛出行程快照不存在错误。
def raise_itinerary_snapshot_not_found(snapshot_id: Optional[str] = None, details: Optional[Any] = None) -> None:
    details = details or {"snapshot_id": snapshot_id, "error": "未找到该行程快照"}
    raise_app_exception(CODE_ITINERARY_SNAPSHOT_NOT_FOUND, details=details)


# 抛出用户偏好标签不存在错误。
def raise_preference_tag_not_found(tag_id: Optional[str] = None, details: Optional[Any] = None) -> None:
    details = details or {"tag_id": tag_id, "error": "未找到该用户偏好标签"}
    raise_app_exception(CODE_PREFERENCE_TAG_NOT_FOUND, details=details)


# 抛出当前会话不在中断状态错误。
def raise_session_not_interrupted(details: Optional[Any] = None, message: Optional[str] = None) -> None:
    raise_app_exception(CODE_SESSION_NOT_INTERRUPTED, message=message, details=details)


# 将 Pydantic 校验错误转换为统一 details 结构。
def _format_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    return [
        {"field": ".".join(str(loc) for loc in error["loc"]), "error": error["msg"]}
        for error in exc.errors()
    ]


# 注册 FastAPI 全局异常处理器。
def setup_exception_handlers(app: FastAPI):
    # 处理显式抛出的业务异常。
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"业务异常: code={exc.code}, message={exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    # 处理 FastAPI/Pydantic 请求参数校验异常。
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = _format_validation_errors(exc)
        logger.warning(f"参数校验失败: {errors}")
        return JSONResponse(
            status_code=ERROR_HTTP_STATUS[CODE_VALIDATION_ERROR],
            content={
                "code": CODE_VALIDATION_ERROR,
                "message": ERROR_MESSAGES[CODE_VALIDATION_ERROR],
                "details": errors,
            },
        )

    # 处理未捕获的系统异常。
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"未捕获异常: {type(exc).__name__}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=ERROR_HTTP_STATUS[CODE_INTERNAL_ERROR],
            content={
                "code": CODE_INTERNAL_ERROR,
                "message": ERROR_MESSAGES[CODE_INTERNAL_ERROR],
                "details": {"error": str(exc) if settings.debug else None},
            },
        )
