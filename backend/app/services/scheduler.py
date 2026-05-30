"""
Scheduler Engine — conflict detection, auto-scheduling, and daily brief generation.
Uses greedy time-slot matching for automatic weekly planning.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.event import Event, PendingTask


class SchedulerEngine:
    """Core scheduling logic."""

    @staticmethod
    def check_conflict(
        db: Session,
        start_time: datetime,
        end_time: datetime,
        exclude_event_id: Optional[str] = None,
    ) -> list[Event]:
        """Check for events that overlap with the given time range."""
        query = db.query(Event).filter(
            Event.status != "cancelled",
            Event.start_time < end_time,
            Event.end_time > start_time,
        )
        if exclude_event_id:
            query = query.filter(Event.id != exclude_event_id)
        return query.order_by(Event.start_time).all()

    @staticmethod
    def find_free_slots(
        db: Session,
        day_start: datetime,
        day_end: datetime,
        min_duration_minutes: int = 30,
    ) -> list[tuple[datetime, datetime]]:
        """Find all free time slots in a given range."""
        events = (
            db.query(Event)
            .filter(
                Event.status != "cancelled",
                Event.start_time < day_end,
                Event.end_time > day_start,
            )
            .order_by(Event.start_time)
            .all()
        )

        free_slots = []
        cursor = day_start

        for event in events:
            if event.start_time > cursor + timedelta(minutes=min_duration_minutes):
                free_slots.append((cursor, event.start_time))
            if event.end_time > cursor:
                cursor = max(cursor, event.end_time)

        if day_end > cursor + timedelta(minutes=min_duration_minutes):
            free_slots.append((cursor, day_end))

        return free_slots

    @staticmethod
    def auto_schedule_week(
        db: Session,
        tasks: list[PendingTask],
        week_start: Optional[datetime] = None,
    ) -> tuple[list[dict], list[str]]:
        """Auto-schedule tasks into free slots using greedy algorithm.

        Returns (scheduled_results, unscheduled_task_ids).
        """
        if week_start is None:
            now = datetime.now()
            week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        # Get all free slots for the week
        all_free_slots = SchedulerEngine.find_free_slots(
            db, week_start, week_end, min_duration_minutes=15
        )

        # Sort tasks by priority (desc) and then by duration (desc)
        sorted_tasks = sorted(
            tasks, key=lambda t: (-t.priority, -t.estimated_duration_minutes)
        )

        scheduled = []
        unscheduled = []

        for task in sorted_tasks:
            duration = timedelta(minutes=task.estimated_duration_minutes)
            placed = False

            for i, (slot_start, slot_end) in enumerate(all_free_slots):
                if slot_end - slot_start >= duration:
                    # Place task at the beginning of this free slot
                    event = Event(
                        title=task.title,
                        description=task.description,
                        start_time=slot_start,
                        end_time=slot_start + duration,
                        priority=task.priority,
                    )
                    db.add(event)
                    db.flush()

                    task.status = "scheduled"
                    task.scheduled_event_id = event.id

                    scheduled.append({
                        "event": event,
                        "slot_start": slot_start,
                        "slot_end": slot_start + duration,
                    })

                    # Update the free slot
                    new_start = slot_start + duration
                    if new_start < slot_end:
                        all_free_slots[i] = (new_start, slot_end)
                    else:
                        all_free_slots.pop(i)

                    placed = True
                    break

            if not placed:
                unscheduled.append(task.title)

        return scheduled, unscheduled

    @staticmethod
    def generate_daily_brief(db: Session, date: Optional[datetime] = None) -> dict:
        """Generate a daily schedule brief including busyness index and reminders."""
        if date is None:
            date = datetime.now()
        day_start = date.replace(hour=settings.working_hour_start, minute=0, second=0, microsecond=0)
        day_end = day_start.replace(hour=settings.working_hour_end)

        events = (
            db.query(Event)
            .filter(
                Event.status != "cancelled",
                Event.start_time < day_end,
                Event.end_time > day_start,
            )
            .order_by(Event.start_time)
            .all()
        )

        free_slots = SchedulerEngine.find_free_slots(db, day_start, day_end, min_duration_minutes=15)

        # Calculate busyness index (0-100)
        total_waking_hours = 16 * 60  # 8am to midnight in minutes
        busy_minutes = sum(
            min((e.end_time - e.start_time).total_seconds() / 60, total_waking_hours)
            for e in events
        )
        busyness = min(int((busy_minutes / total_waking_hours) * 100), 100)

        free_slot_dicts = [
            {"start": s.isoformat(), "end": e.isoformat()}
            for s, e in free_slots
        ]

        # Include reminders for today's events
        from ..models.reminder import Reminder
        event_ids = [e.id for e in events]
        today_reminders = []
        if event_ids:
            today_reminders = (
                db.query(Reminder)
                .filter(
                    Reminder.event_id.in_(event_ids),
                    Reminder.status == "pending",
                )
                .all()
            )

        # Build summary
        event_count = len(events)
        if event_count == 0:
            summary = "今天没有日程安排，尽情享受空闲时光吧！"
        elif busyness < 30:
            summary = f"今天比较轻松，共有{event_count}个日程，有充足的自由时间。"
        elif busyness < 60:
            summary = f"今天安排适中，共有{event_count}个日程，请注意时间分配。"
        elif busyness < 85:
            summary = f"今天比较忙碌，共有{event_count}个日程，建议合理安排休息。"
        else:
            summary = f"今天非常繁忙，共有{event_count}个日程，请注意劳逸结合！"

        return {
            "date": day_start.strftime("%Y-%m-%d"),
            "events_today": events,
            "free_slots": free_slot_dicts,
            "busyness_index": busyness,
            "summary": summary,
            "reminders": [
                {
                    "id": r.id,
                    "event_id": r.event_id,
                    "title": r.title,
                    "remind_at": r.remind_at.isoformat(),
                    "message": r.message,
                }
                for r in today_reminders
            ],
        }

    @staticmethod
    def suggest_alternative_slots(
        db: Session,
        start_time: datetime,
        duration_minutes: int,
        look_ahead_days: int = 3,
    ) -> list[tuple[datetime, datetime]]:
        """Find alternative time slots when a conflict is detected."""
        day_start = start_time.replace(hour=8, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=look_ahead_days)

        free_slots = SchedulerEngine.find_free_slots(
            db, day_start, day_end, min_duration_minutes=duration_minutes
        )

        duration = timedelta(minutes=duration_minutes)
        alternatives = []
        for slot_start, slot_end in free_slots:
            if slot_end - slot_start >= duration:
                alternatives.append((slot_start, slot_start + duration))
                if len(alternatives) >= 3:
                    break

        return alternatives


scheduler = SchedulerEngine()
