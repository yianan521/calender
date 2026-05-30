from datetime import datetime, timezone, timedelta
from typing import Optional

from pydantic import BaseModel, Field, field_serializer

# Local timezone (UTC+8)
LOCAL_TZ = timezone(timedelta(hours=8))


class EventCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str = ""
    location: str = ""
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    priority: int = Field(default=0, ge=0, le=2)
    status: str = "confirmed"
    rrule: str = ""


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=2)
    status: Optional[str] = None
    rrule: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: str
    location: str
    start_time: datetime
    end_time: datetime
    all_day: bool
    priority: int
    status: str
    rrule: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('start_time', 'end_time', 'created_at', 'updated_at')
    def serialize_dt(self, dt: datetime) -> str:
        """Serialize naive datetime as local ISO with +08:00 offset so JS doesn't misparse."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.isoformat()
