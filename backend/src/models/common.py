from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """单个字段或业务错误的详情。"""

    field: str | None = None
    error: str


class ErrorResponse(BaseModel):
    """所有 JSON 错误响应的统一结构。"""

    code: int
    message: str
    details: list[ErrorDetail] | dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    """所有 JSON 成功响应的统一结构。"""

    code: int
    message: str
    data: T | None = None
