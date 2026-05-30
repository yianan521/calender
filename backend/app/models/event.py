"""Event and PendingTask ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import relationship

from ..database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    location = Column(String(512), default="")
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    priority = Column(Integer, default=0)  # 0=normal, 1=high, 2=urgent
    status = Column(String(20), default="confirmed")  # confirmed, tentative, cancelled
    rrule = Column(String(255), default="")  # RRULE string for recurring events
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class PendingTask(Base):
    __tablename__ = "pending_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    estimated_duration_minutes = Column(Integer, default=60)
    priority = Column(Integer, default=0)
    deadline = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending, scheduled, completed
    scheduled_event_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
