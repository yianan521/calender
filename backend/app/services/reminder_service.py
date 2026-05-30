"""
Reminder Service — manages reminder lifecycle, polling, and commute-tied reminders.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models.event import Event
from ..models.reminder import Reminder


class ReminderService:
    """Manages reminder CRUD, polling, and auto-generation."""

    @staticmethod
    def create_for_event(
        db: Session,
        event: Event,
        advance_minutes: int = 15,
        remind_type: str = "popup",
    ) -> Reminder:
        """Create a reminder for an existing event."""
        remind_at = event.start_time - timedelta(minutes=advance_minutes)

        # Avoid creating duplicate reminders for the same event + time
        existing = (
            db.query(Reminder)
            .filter(
                Reminder.event_id == event.id,
                Reminder.remind_at == remind_at,
            )
            .first()
        )
        if existing:
            return existing

        reminder = Reminder(
            event_id=event.id,
            title=f"提醒：{event.title}",
            remind_at=remind_at,
            remind_type=remind_type,
            advance_minutes=advance_minutes,
            message=f"「{event.title}」将在{advance_minutes}分钟后开始。"
            if event.location
            else f"「{event.title}」将在{advance_minutes}分钟后开始",
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    @staticmethod
    def create_commute_reminder(
        db: Session,
        event: Event,
        origin: str,
        commute_minutes: int,
        buffer_minutes: int = 10,
    ) -> Reminder:
        """Create a departure reminder with commute time factored in."""
        total_advance = commute_minutes + buffer_minutes
        remind_at = event.start_time - timedelta(minutes=total_advance)

        reminder = Reminder(
            event_id=event.id,
            title=f"出发提醒：{event.title}",
            remind_at=remind_at,
            remind_type="commute",
            advance_minutes=total_advance,
            message=f"该出发了！前往「{event.title}」需要约{commute_minutes}分钟（{buffer_minutes}分钟缓冲）。",
            commute_origin=origin,
            commute_minutes=commute_minutes,
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder

    @staticmethod
    def get_pending_reminders(
        db: Session, window_minutes: int = 60
    ) -> list[Reminder]:
        """Get reminders that are due within the next window_minutes (or overdue)."""
        now = datetime.now()
        cutoff = now + timedelta(minutes=window_minutes)
        return (
            db.query(Reminder)
            .filter(
                Reminder.status == "pending",
                Reminder.remind_at <= cutoff,
            )
            .order_by(Reminder.remind_at)
            .all()
        )

    @staticmethod
    def get_upcoming_reminders(
        db: Session, hours: int = 5
    ) -> list[Reminder]:
        """Get all pending reminders in the next N hours for display."""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)
        return (
            db.query(Reminder)
            .filter(
                Reminder.status == "pending",
                Reminder.remind_at >= now,
                Reminder.remind_at <= cutoff,
            )
            .order_by(Reminder.remind_at)
            .all()
        )

    @staticmethod
    def get_events_within_5_hours(db: Session) -> list[Event]:
        """Get events starting within the next 5 hours for the reminder panel."""
        now = datetime.now()
        cutoff = now + timedelta(hours=5)
        return (
            db.query(Event)
            .filter(
                Event.status != "cancelled",
                Event.start_time >= now,
                Event.start_time <= cutoff,
            )
            .order_by(Event.start_time)
            .all()
        )

    @staticmethod
    def mark_triggered(db: Session, reminder_id: str):
        """Mark a reminder as triggered."""
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.status = "triggered"
            db.commit()

    @staticmethod
    def dismiss(db: Session, reminder_id: str):
        """Dismiss a reminder."""
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.status = "dismissed"
            db.commit()

    @staticmethod
    def delete_for_event(db: Session, event_id: str) -> int:
        """Delete all reminders tied to an event. Returns count deleted."""
        count = (
            db.query(Reminder)
            .filter(Reminder.event_id == event_id)
            .delete()
        )
        db.commit()
        return count


reminder_service = ReminderService()
