from typing import Any, Optional
from pydantic import BaseModel, Field

class AdoptReferenceRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    start_date: str
    duration: int = Field(gt=0)
    travelers: int = Field(gt=0)
    destination: Optional[str] = None
    structured_preferences: Optional[dict[str, Any]] = None
