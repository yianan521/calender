from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .event import EventResponse


class ScheduleRequest(BaseModel):
    tasks: list[str]  # natural language task descriptions
    week_start: Optional[datetime] = None


class ConflictResponse(BaseModel):
    has_conflict: bool
    conflicting_events: list[EventResponse] = []
    suggestion: str = ""


class ScheduleResult(BaseModel):
    event: EventResponse
    slot_start: datetime
    slot_end: datetime


class ScheduleResponse(BaseModel):
    scheduled: list[ScheduleResult] = []
    unscheduled: list[str] = []
    message: str = ""


class DailyBrief(BaseModel):
    date: str
    events_today: list[EventResponse]
    free_slots: list[dict]
    busyness_index: int  # 0-100
    summary: str
    reminders: list[dict] = []
