from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from src.models.common import ApiResponse


class SessionItem(BaseModel):
    """历史会话列表中的单条行程摘要。"""

    thread_id: str
    destination: str | None = None
    start_date: str | None = None
    duration: int | None = None
    status: Literal["planning", "confirmed", "completed", "failed", "deleted"]
    last_updated: str


class SessionListData(BaseModel):
    """历史会话列表分页数据。"""

    sessions: list[SessionItem]
    next_cursor: str | None
    has_more: bool


class SessionSnapshotData(BaseModel):
    """会话运行快照。"""

    session_id: str
    state: dict[str, Any]
    graph_structure: dict[str, Any]
    metadata: dict[str, Any]
    created_at: str


class SessionListResponse(ApiResponse[SessionListData]):
    """历史会话列表统一响应。"""
