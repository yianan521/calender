"""Event CRUD routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.event import Event
from ..schemas.event import EventCreate, EventResponse, EventUpdate
from ..services.scheduler import scheduler

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventResponse])
def list_events(
    start: Optional[datetime] = Query(None, description="Filter events from this time"),
    end: Optional[datetime] = Query(None, description="Filter events until this time"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if start:
        query = query.filter(Event.end_time > start)
    if end:
        query = query.filter(Event.start_time < end)
    if status:
        query = query.filter(Event.status == status)
    return query.order_by(Event.start_time).all()


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/", response_model=EventResponse, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    # Validate time range
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    # Check for conflicts
    conflicts = scheduler.check_conflict(db, payload.start_time, payload.end_time)
    if conflicts and payload.status == "confirmed":
        conflict_titles = [e.title for e in conflicts]
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Time conflict detected",
                "conflicting_events": conflict_titles,
            },
        )

    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.put("/{event_id}", response_model=EventResponse)
def update_event(event_id: str, payload: EventUpdate, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Validate updated time range
    new_start = update_data.get("start_time", event.start_time)
    new_end = update_data.get("end_time", event.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    for key, value in update_data.items():
        setattr(event, key, value)

    event.updated_at = datetime.now()
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    return None


@router.get("/check-conflict/{event_id}", response_model=dict)
def check_event_conflict(event_id: str, db: Session = Depends(get_db)):
    """Check if a specific event has conflicts."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    conflicts = scheduler.check_conflict(
        db, event.start_time, event.end_time, exclude_event_id=event_id
    )
    return {
        "has_conflict": len(conflicts) > 0,
        "conflicting_events": [
            {"id": e.id, "title": e.title, "start_time": e.start_time.isoformat()}
            for e in conflicts
        ],
    }
