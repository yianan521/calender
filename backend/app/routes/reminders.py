"""Reminder routes — CRUD, commute check, and upcoming-reminders polling."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.reminder import Reminder
from ..models.event import Event
from ..schemas.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
    CommuteRequest,
    CommuteResponse,
)
from ..services.reminder_service import reminder_service
from ..services.map_service import map_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


# ── CRUD ──────────────────────────────────────────────


@router.get("/", response_model=list[ReminderResponse])
def list_reminders(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Reminder)
    if status:
        query = query.filter(Reminder.status == status)
    return query.order_by(Reminder.remind_at).all()


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(reminder_id: str, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.post("/", response_model=ReminderResponse, status_code=201)
def create_reminder(payload: ReminderCreate, db: Session = Depends(get_db)):
    reminder = Reminder(**payload.model_dump())
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.put("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(reminder_id: str, payload: ReminderUpdate, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(reminder, key, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: str, db: Session = Depends(get_db)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return None


# ── Specialised endpoints ─────────────────────────────


@router.post("/commute", response_model=CommuteResponse)
async def check_commute(payload: CommuteRequest, db: Session = Depends(get_db)):
    """Calculate commute time and suggested departure."""
    info = await map_service.get_commute_info(payload.origin, payload.destination)
    departure = map_service.calculate_departure_time(
        payload.event_start_time, info["commute_minutes"]
    )

    return CommuteResponse(
        commute_minutes=info["commute_minutes"],
        commute_distance_km=info["distance_km"],
        suggested_departure_time=departure,
        routes=info.get("routes", []),
    )


@router.post("/commute/create", response_model=ReminderResponse)
async def create_commute_reminder(payload: CommuteRequest, db: Session = Depends(get_db)):
    """Create a departure reminder based on commute time."""
    if not payload.event_id:
        raise HTTPException(status_code=400, detail="event_id is required")

    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    info = await map_service.get_commute_info(payload.origin, payload.destination)

    reminder = reminder_service.create_commute_reminder(
        db,
        event=event,
        origin=payload.origin,
        commute_minutes=info["commute_minutes"],
    )
    return reminder


@router.get("/poll/pending", response_model=list[ReminderResponse])
def poll_pending_reminders(
    window_minutes: int = 60,
    db: Session = Depends(get_db),
):
    """Get reminders that are due or upcoming (for frontend polling)."""
    return reminder_service.get_pending_reminders(db, window_minutes)


@router.get("/events/5hours", response_model=dict)
def get_events_5hours(db: Session = Depends(get_db)):
    """Get events starting within the next 5 hours and their reminders."""
    events = reminder_service.get_events_within_5_hours(db)
    reminders = reminder_service.get_upcoming_reminders(db, hours=5)

    return {
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat(),
                "location": e.location,
                "priority": e.priority,
            }
            for e in events
        ],
        "reminders": [
            {
                "id": r.id,
                "event_id": r.event_id,
                "title": r.title,
                "remind_at": r.remind_at.isoformat(),
                "remind_type": r.remind_type,
                "message": r.message,
                "status": r.status,
                "commute_origin": r.commute_origin,
                "commute_minutes": r.commute_minutes,
            }
            for r in reminders
        ],
    }


@router.post("/{reminder_id}/trigger", response_model=ReminderResponse)
def trigger_reminder(reminder_id: str, db: Session = Depends(get_db)):
    """Mark a reminder as triggered (dismissed by user)."""
    reminder_service.mark_triggered(db, reminder_id)
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    return reminder


@router.post("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(reminder_id: str, db: Session = Depends(get_db)):
    """Dismiss a reminder."""
    reminder_service.dismiss(db, reminder_id)
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    return reminder
