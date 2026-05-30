"""Pending tasks CRUD routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.event import PendingTask
from ..schemas.task import PendingTaskCreate, PendingTaskResponse, PendingTaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=list[PendingTaskResponse])
def list_tasks(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(PendingTask)
    if status:
        query = query.filter(PendingTask.status == status)
    return query.order_by(PendingTask.priority.desc(), PendingTask.created_at).all()


@router.get("/{task_id}", response_model=PendingTaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(PendingTask).filter(PendingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=PendingTaskResponse, status_code=201)
def create_task(payload: PendingTaskCreate, db: Session = Depends(get_db)):
    task = PendingTask(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=PendingTaskResponse)
def update_task(task_id: str, payload: PendingTaskUpdate, db: Session = Depends(get_db)):
    task = db.query(PendingTask).filter(PendingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(PendingTask).filter(PendingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None
