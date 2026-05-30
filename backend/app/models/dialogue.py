"""DialogueSession and DialogueMessage ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, JSON
from sqlalchemy.orm import relationship

from ..database import Base


class DialogueSession(Base):
    __tablename__ = "dialogue_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(20), default="active")  # active, completed
    pending_question = Column(String(50), nullable=True)  # e.g. "commute", "reminder", "title"
    pending_event_id = Column(String(36), nullable=True)  # event id for follow-ups
    pending_intent_json = Column(JSON, nullable=True)  # the last parsed intent awaiting slots
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DialogueMessage(Base):
    __tablename__ = "dialogue_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    intent_json = Column(JSON, nullable=True)  # structured intent/entity data
    created_at = Column(DateTime, default=datetime.now)
