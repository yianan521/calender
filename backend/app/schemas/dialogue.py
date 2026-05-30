from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DialogueSessionResponse(BaseModel):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DialogueMessageCreate(BaseModel):
    session_id: str
    role: str = "user"
    content: str
    intent_json: Optional[dict] = None


class DialogueMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    intent_json: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class DialogueRequest(BaseModel):
    session_id: Optional[str] = None
    text: str = Field(..., min_length=1)


class DialogueResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[dict] = None
    action: Optional[dict] = None
