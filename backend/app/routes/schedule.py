"""Schedule routes — auto-scheduling, conflict detection, daily brief."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.event import Event, PendingTask
from ..schemas.schedule import ScheduleRequest, ScheduleResponse, ConflictResponse, DailyBrief
from ..services.scheduler import scheduler

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.post("/auto", response_model=ScheduleResponse)
def auto_schedule(payload: ScheduleRequest, db: Session = Depends(get_db)):
    """Auto-schedule pending tasks into free time slots."""
    tasks = []
    for desc in payload.tasks:
        task = PendingTask(
            title=desc.strip(),
            estimated_duration_minutes=60,
            priority=0,
        )
        db.add(task)
        tasks.append(task)

    scheduled, unscheduled = scheduler.auto_schedule_week(db, tasks, payload.week_start)
    db.commit()

    results = []
    for item in scheduled:
        ev = item["event"]
        results.append({
            "event": ev,
            "slot_start": item["slot_start"],
            "slot_end": item["slot_end"],
        })

    message = f"已安排{len(scheduled)}个事项"
    if unscheduled:
        message += f"，{len(unscheduled)}个未安排"

    return ScheduleResponse(
        scheduled=results,
        unscheduled=unscheduled,
        message=message,
    )


@router.get("/conflicts", response_model=ConflictResponse)
def check_conflicts(
    start: datetime = Query(..., description="Start time (ISO 8601)"),
    end: datetime = Query(..., description="End time (ISO 8601)"),
    db: Session = Depends(get_db),
):
    """Check for time conflicts in a given range."""
    conflicts = scheduler.check_conflict(db, start, end)
    if not conflicts:
        return ConflictResponse(has_conflict=False, suggestion="该时段空闲，可以安排日程。")

    suggestion = ""
    duration = int((end - start).total_seconds() / 60)
    alternatives = scheduler.suggest_alternative_slots(db, start, duration)
    if alternatives:
        times = [a[0].strftime("%m/%d %H:%M") for a in alternatives[:3]]
        suggestion = f"可选时段：{'、'.join(times)}"

    return ConflictResponse(
        has_conflict=True,
        conflicting_events=[e for e in conflicts],
        suggestion=suggestion,
    )


@router.get("/free-slots")
def get_free_slots(
    day: Optional[str] = Query(None, description="Date string YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
):
    """Get free time slots for a given day."""
    if day:
        date = datetime.fromisoformat(day)
    else:
        date = datetime.now()

    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    slots = scheduler.find_free_slots(db, day_start, day_end, min_duration_minutes=15)
    return {
        "date": day_start.strftime("%Y-%m-%d"),
        "free_slots": [
            {"start": s.isoformat(), "end": e.isoformat()} for s, e in slots
        ],
    }


@router.get("/daily-brief", response_model=DailyBrief)
def daily_brief(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD, defaults to today"),
    db: Session = Depends(get_db),
):
    """Generate a daily schedule brief with busyness index."""
    dt = datetime.fromisoformat(date) if date else datetime.now()
    brief = scheduler.generate_daily_brief(db, dt)
    return DailyBrief(**brief)
