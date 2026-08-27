from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

PreferenceCategory = Literal[
    "diet",
    "pace",
    "budget",
    "interest",
    "accommodation",
    "transport",
]
PreferenceSource = Literal["inferred", "manual"]


class PreferenceItem(BaseModel):
    id: str
    category: PreferenceCategory
    content: str
    source: PreferenceSource
    confidence: float = Field(ge=0, le=1)
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class PreferenceSummary(BaseModel):
    total: int
    active_count: int
    categories: dict[str, int]


class PreferenceListData(BaseModel):
    preferences: list[PreferenceItem]
    summary: PreferenceSummary


class AddPreferenceRequest(BaseModel):
    category: PreferenceCategory
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty")
        return value


class UpdatePreferenceRequest(BaseModel):
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty")
        return value


class PreferenceDeletionData(BaseModel):
    id: str
    is_active: bool
    deleted_at: datetime


class AddPreferenceOperation(AddPreferenceRequest):
    """批量操作中的新增偏好项。"""

    action: Literal["add"] = "add"


class UpdatePreferenceOperation(UpdatePreferenceRequest):
    """批量操作中的修改偏好项。"""

    action: Literal["update"] = "update"
    id: str = Field(min_length=1)


class DeletePreferenceRequest(BaseModel):
    """批量操作中的删除偏好项。"""

    action: Literal["delete"] = "delete"
    id: str = Field(min_length=1)


PreferenceOperation = Annotated[
    AddPreferenceOperation | UpdatePreferenceOperation | DeletePreferenceRequest,
    Field(discriminator="action"),
]


class BatchPreferenceRequest(BaseModel):
    """用户画像说明书中定义的批量偏好操作请求。"""

    action: Literal["batch"] = "batch"
    operations: list[PreferenceOperation] = Field(min_length=1)


class PreferenceItemInput(BaseModel):
    """整体替换偏好时单条输入。"""

    category: PreferenceCategory
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty")
        return value


class ReplacePreferencesRequest(BaseModel):
    """整体替换用户手动偏好（保留推断偏好不动）。"""

    items: list[PreferenceItemInput] = Field(default_factory=list)
