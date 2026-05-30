"""
Dialogue Manager — maintains session state machine for multi-turn conversations.
Handles context tracking, correction detection, and follow-up prompting.

State is persisted to the DB via DialogueSession so it survives restarts.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

CORRECTION_KEYWORDS = ["不对", "改成", "还是", "算了", "不是", "换", "修改", "更正"]

CONFIRMATION_KEYWORDS = ["好的", "好", "是的", "对", "嗯", "可以", "行", "需要", "ok", "yes", "嗯嗯", "要得", "当然", "没问题"]


class DialogueState:
    """Tracks the current state of a dialogue session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.context: dict = {}
        self.history: list[dict] = []
        self.pending_intent: Optional[dict] = None
        self.missing_slots: list[str] = []
        self.awaiting_confirmation: bool = False
        # Follow-up context: tracks what the assistant just asked about
        self.pending_question: Optional[str] = None  # e.g. "commute", "reminder"
        self.pending_event_id: Optional[str] = None

    def restore_from_db(self, db_session, db: Session):
        """Restore conversation history from DB messages and session state."""
        from ..models.dialogue import DialogueMessage

        # Restore pending state from the DB session row
        if db_session.pending_question:
            self.pending_question = db_session.pending_question
        if db_session.pending_event_id:
            self.pending_event_id = db_session.pending_event_id
        if db_session.pending_intent_json:
            self.pending_intent = db_session.pending_intent_json

        # Rebuild conversation history from the last 20 DB messages
        messages = (
            db.query(DialogueMessage)
            .filter(DialogueMessage.session_id == self.session_id)
            .order_by(DialogueMessage.created_at)
            .all()
        )
        for msg in messages[-20:]:
            self.history.append({
                "role": msg.role,
                "content": msg.content,
                "intent": msg.intent_json,
                "timestamp": msg.created_at.isoformat() if msg.created_at else datetime.now().isoformat(),
            })

    def save_to_db(self, db_session):
        """Persist volatile state back to the DialogueSession row."""
        db_session.pending_question = self.pending_question
        db_session.pending_event_id = self.pending_event_id
        db_session.pending_intent_json = self.pending_intent
        db_session.updated_at = datetime.now()

    def add_turn(self, role: str, content: str, intent: Optional[dict] = None):
        self.history.append({
            "role": role,
            "content": content,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })

    def get_context_for_llm(self) -> list[dict]:
        """Return recent history formatted for LLM context window."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.history[-20:]  # last 20 turns
        ]

    def is_confirming(self, text: str) -> bool:
        """Check if the user is saying yes to a pending question.
        Only short texts are considered confirmations to avoid misclassifying commands."""
        stripped = text.strip()
        if len(stripped) > 8:
            return False
        return any(kw == stripped.lower() or kw in stripped.lower() for kw in CONFIRMATION_KEYWORDS)


class DialogueManager:
    """Manages multiple dialogue sessions with optional DB persistence."""

    def __init__(self):
        self._sessions: dict[str, DialogueState] = {}

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> DialogueState:
        # Check in-memory cache first
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        if not session_id:
            session_id = self._generate_id()

        state = DialogueState(session_id)

        # Try to restore from DB if available
        if db:
            from ..models.dialogue import DialogueSession as DialogueSessionModel
            db_session = db.query(DialogueSessionModel).filter(
                DialogueSessionModel.id == session_id
            ).first()
            if db_session:
                state.restore_from_db(db_session, db)

        self._sessions[session_id] = state
        return state

    @staticmethod
    def _generate_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def detect_correction(self, text: str) -> tuple[bool, str]:
        """Detect if user is correcting themselves and extract the corrected intent."""
        for kw in CORRECTION_KEYWORDS:
            if kw in text:
                idx = text.find(kw)
                corrected = text[idx + len(kw):].strip()
                return True, corrected
        return False, text

    def identify_missing_slots(self, intent: dict) -> list[str]:
        """Check which required slots are missing from an intent."""
        missing = []
        intent_type = intent.get("intent", "")

        if intent_type == "create_event":
            if not intent.get("title"):
                missing.append("title")
            if not intent.get("start_time"):
                missing.append("start_time")
        elif intent_type == "query_events":
            pass  # queries can be vague
        elif intent_type == "update_event":
            if not intent.get("event_id"):
                missing.append("event_id")

        return missing

    def generate_follow_up(self, missing_slots: list[str]) -> str:
        """Generate a natural follow-up question for missing slots."""
        prompts = {
            "title": "请问这个日程的标题是什么？",
            "start_time": "请问安排在什么时间？",
            "event_id": "请问要修改哪个日程？",
        }
        questions = [prompts.get(s, f"请提供{s}") for s in missing_slots]
        return "；".join(questions)

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Remove in-memory sessions older than the specified age."""
        cutoff = datetime.now()
        stale = [
            sid for sid, s in self._sessions.items()
            if s.history and
            (cutoff - datetime.fromisoformat(s.history[-1]["timestamp"])).total_seconds() > max_age_hours * 3600
        ]
        for sid in stale:
            del self._sessions[sid]


dialogue_manager = DialogueManager()
