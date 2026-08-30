from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StructuredPreferencesInput(BaseModel):
    """前端传入的结构化旅行偏好（中文展示标签）。

    与内部 blackboard.structured_preferences（英文枚举）不同，这里保留前端
    展示用的中文取值，由 preferences_parser 负责映射为后端可消费的英文枚举。
    字段类型保持宽松（字符串而非严格枚举），未识别的值由解析函数安全忽略，
    避免单个未知选项导致整条请求 422。
    """

    budget_level: Optional[str] = None
    start_date: Optional[str] = None
    pace: Optional[str] = None
    interests: Optional[list[str]] = None
    travelers: Optional[int] = None
    travelers_type: Optional[str] = None
    hotel_preference: Optional[str] = None
    lodging_mode: Optional[str] = None
    lodging_mode: Optional[str] = None
    intercity_transport: Optional[str] = None
    local_transport: Optional[str] = None
    origin: Optional[str] = None
    include_return: Optional[bool] = True


class ChatStreamRequest(BaseModel):
    """发起或继续对话的请求体。"""

    thread_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    current_time: str | None = None
    structured_input: StructuredPreferencesInput | None = None

    @field_validator("thread_id", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class UserDecision(BaseModel):
    """恢复中断流程时提交的用户决策。"""

    action: str
    hint: str | None = None
    note: str | None = None


class ResumeRequest(BaseModel):
    """恢复中断流程的请求体。"""

    thread_id: str = Field(min_length=1)
    user_decision: UserDecision


class LogisticsConfirmationRequest(BaseModel):
    """确认一个规则估算的住宿或城际交通方案。"""

    thread_id: str = Field(min_length=1)
    item_key: str = Field(min_length=1)


class StopChatData(BaseModel):
    """停止生成后的会话状态。"""

    thread_id: str
    stopped_at: str
    partial_tokens: int
    has_partial_result: bool
    tip: str
