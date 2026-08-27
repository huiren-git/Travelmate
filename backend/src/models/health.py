from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthData(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    components: dict[str, dict[str, Any]]


class ServiceInfoData(BaseModel):
    """服务根路径探针数据。"""

    service: str
    version: str
    status: str
