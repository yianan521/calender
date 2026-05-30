from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReminderCreate(BaseModel):
    title: str = Field(..., max_length=255)
    event_id: Optional[str] = None
    remind_at: datetime
    remind_type: str = "popup"
    advance_minutes: int = Field(default=15, ge=0)
    message: str = ""
    commute_origin: str = ""
    commute_minutes: int = 0


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    remind_at: Optional[datetime] = None
    remind_type: Optional[str] = None
    advance_minutes: Optional[int] = None
    message: Optional[str] = None
    status: Optional[str] = None
    commute_origin: Optional[str] = None
    commute_minutes: Optional[int] = None


class ReminderResponse(BaseModel):
    id: str
    event_id: Optional[str]
    title: str
    remind_at: datetime
    remind_type: str
    advance_minutes: int
    message: str
    status: str
    commute_origin: str
    commute_minutes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CommuteRequest(BaseModel):
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    event_id: Optional[str] = None
    event_start_time: datetime


class CommuteResponse(BaseModel):
    commute_minutes: int
    commute_distance_km: float
    suggested_departure_time: datetime
    routes: list[dict] = []
