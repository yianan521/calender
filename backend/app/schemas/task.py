from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PendingTaskCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str = ""
    estimated_duration_minutes: int = Field(default=60, gt=0)
    priority: int = Field(default=0, ge=0, le=2)
    deadline: Optional[datetime] = None


class PendingTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    estimated_duration_minutes: Optional[int] = Field(None, gt=0)
    priority: Optional[int] = Field(None, ge=0, le=2)
    deadline: Optional[datetime] = None
    status: Optional[str] = None
    scheduled_event_id: Optional[str] = None


class PendingTaskResponse(BaseModel):
    id: str
    title: str
    description: str
    estimated_duration_minutes: int
    priority: int
    deadline: Optional[datetime]
    status: str
    scheduled_event_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
