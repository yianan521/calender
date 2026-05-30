"""Reminder ORM model — supports popup, voice, and commute-based reminders."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    remind_at = Column(DateTime, nullable=False, index=True)
    remind_type = Column(String(20), default="popup")  # popup, voice, email
    advance_minutes = Column(Integer, default=15)  # minutes before event
    message = Column(Text, default="")
    status = Column(String(20), default="pending")  # pending, triggered, dismissed
    commute_origin = Column(String(512), default="")  # for commute-based reminders
    commute_minutes = Column(Integer, default=0)  # estimated travel time
    created_at = Column(DateTime, default=datetime.now)

    event = relationship("Event", backref="reminders")
