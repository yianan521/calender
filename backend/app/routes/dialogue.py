"""Dialogue route — voice/text input processing with NLU."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.dialogue import DialogueSession, DialogueMessage
from ..models.event import Event, PendingTask
from ..models.reminder import Reminder
from ..schemas.dialogue import (
    DialogueRequest,
    DialogueResponse,
    DialogueSessionResponse,
    DialogueMessageResponse,
)
from ..services.dialogue_manager import dialogue_manager
from ..services.nlu_service import nlu_service
from ..services.scheduler import scheduler
from ..services.reminder_service import reminder_service
from ..services.map_service import map_service

router = APIRouter(prefix="/dialogue", tags=["dialogue"])


@router.get("/sessions", response_model=list[DialogueSessionResponse])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(DialogueSession).order_by(DialogueSession.updated_at.desc()).all()


@router.get("/sessions/{session_id}", response_model=DialogueSessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(DialogueSession).filter(DialogueSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[DialogueMessageResponse])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    return (
        db.query(DialogueMessage)
        .filter(DialogueMessage.session_id == session_id)
        .order_by(DialogueMessage.created_at)
        .all()
    )


@router.post("/", response_model=DialogueResponse)
async def process_dialogue(payload: DialogueRequest, db: Session = Depends(get_db)):
    """Process a natural language input and return assistant response with actions."""
    # Get or create dialogue state (restore from DB if available)
    state = dialogue_manager.get_or_create_session(payload.session_id, db=db)

    # Ensure DB session row exists
    db_session = db.query(DialogueSession).filter(
        DialogueSession.id == state.session_id
    ).first()
    if not db_session:
        db_session = DialogueSession(id=state.session_id)
        db.add(db_session)

    # Detect self-correction
    is_correction, cleaned_text = dialogue_manager.detect_correction(payload.text)
    if is_correction:
        # In correction mode, discard prior intent for this turn
        state.pending_intent = None

    # Save user message
    user_msg = DialogueMessage(
        session_id=state.session_id,
        role="user",
        content=payload.text,
    )
    db.add(user_msg)

    # Check for confirmation (user says "yes" to a pending follow-up question)
    is_confirming = state.is_confirming(cleaned_text)
    reply = ""
    action = None

    if is_confirming and state.pending_question == "commute" and state.pending_event_id:
        # User confirmed they want commute time calculation
        reply, action = await _handle_commute_followup(state.pending_event_id, db)
        state.pending_question = None
        state.pending_event_id = None
        intent = {"intent": "commute_check", "confidence": 1.0}
    elif is_confirming and state.pending_question is None:
        # Generic confirmation without pending question — treat as general chat
        intent = await nlu_service.parse(cleaned_text, state.get_context_for_llm())
        reply, action = _handle_chat(intent, state), None
    else:
        # Get NLU parsing
        context = state.get_context_for_llm()
        intent = await nlu_service.parse(cleaned_text, context)

        # Check for missing slots
        missing = dialogue_manager.identify_missing_slots(intent)

        if missing and intent.get("intent") in ("create_event", "update_event", "set_reminder"):
            # Ask follow-up question
            reply = dialogue_manager.generate_follow_up(missing)
            state.missing_slots = missing
            state.pending_intent = intent
        elif intent.get("needs_clarification"):
            reply = intent.get("clarification_question", "请问能再详细说明一下吗？")
        else:
            # Execute the intent
            reply, action = await _execute_intent(intent, state, db)

    # Save assistant message
    assistant_msg = DialogueMessage(
        session_id=state.session_id,
        role="assistant",
        content=reply,
        intent_json=intent,
    )
    db.add(assistant_msg)

    # Update state
    state.add_turn("user", payload.text, intent)
    state.add_turn("assistant", reply)

    # Save volatile state to DB so it survives restarts
    state.save_to_db(db_session)

    db_session.updated_at = datetime.now()
    db.commit()

    return DialogueResponse(
        session_id=state.session_id,
        reply=reply,
        intent=intent,
        action=action,
    )


async def _execute_intent(intent: dict, state, db: Session) -> tuple[str, dict | None]:
    """Execute the parsed intent and return (reply, action_dict)."""
    intent_type = intent.get("intent", "general_chat")

    if intent_type == "create_event":
        return await _handle_create_event(intent, state, db)
    elif intent_type == "query_events":
        return _handle_query_events(intent, db)
    elif intent_type == "update_event":
        return await _handle_update_event(intent, db)
    elif intent_type == "delete_event":
        return _handle_delete_event(intent, db)
    elif intent_type == "auto_schedule":
        return _handle_auto_schedule(intent, db)
    elif intent_type == "set_reminder":
        return await _handle_set_reminder(intent, db)
    else:
        return _handle_chat(intent, state), None


async def _handle_create_event(intent: dict, state, db: Session) -> tuple[str, dict | None]:
    """Create an event from parsed intent."""
    title = intent.get("title", "未命名日程")
    start_str = intent.get("start_time")
    end_str = intent.get("end_time")

    if not start_str:
        return "请问这个日程安排在什么时间呢？", None

    try:
        start_time = datetime.fromisoformat(start_str)
        end_time = datetime.fromisoformat(end_str) if end_str else start_time + timedelta(hours=1)
    except (ValueError, TypeError):
        return "抱歉，我没能理解这个时间，能再描述一下吗？", None

    # Conflict check
    conflicts = scheduler.check_conflict(db, start_time, end_time)
    if conflicts:
        conflict_names = "、".join([e.title for e in conflicts[:3]])
        alternatives = scheduler.suggest_alternative_slots(
            db, start_time, int((end_time - start_time).total_seconds() / 60)
        )
        alt_text = ""
        if alternatives:
            alt_text = f"建议安排在{alternatives[0][0].strftime('%H:%M')}或{alternatives[1][0].strftime('%H:%M')}" if len(alternatives) > 1 else f"建议安排在{alternatives[0][0].strftime('%H:%M')}"

        return (
            f"检测到该时段与「{conflict_names}」冲突。{alt_text}，需要为您调整吗？"
        ), {"type": "conflict", "alternatives": [(a.isoformat(), b.isoformat()) for a, b in alternatives]}

    event = Event(
        title=title,
        description=intent.get("description", ""),
        location=intent.get("location", ""),
        start_time=start_time,
        end_time=end_time,
        priority=intent.get("priority", 0),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Auto-create a default 15-min reminder
    advance = intent.get("advance_minutes", 15)
    reminder = reminder_service.create_for_event(db, event, advance_minutes=advance)

    time_desc = f"{start_time.strftime('%m月%d日 %H:%M')}"
    reply = f"已为您创建日程「{title}」，时间：{time_desc}，已设置提前{advance}分钟提醒。"
    if intent.get("location"):
        reply += f"\n地点在{intent.get('location')}，需要帮您计算通勤时间并设置出发提醒吗？"
        state.pending_question = "commute"
        state.pending_event_id = event.id
    return reply, {
        "type": "event_created",
        "event_id": event.id,
        "reminder_id": reminder.id,
        "remind_at": reminder.remind_at.isoformat(),
    }


def _handle_query_events(intent: dict, db: Session) -> tuple[str, dict | None]:
    """Query events by time range."""
    now = datetime.now()
    start_str = intent.get("start_time")
    if start_str:
        try:
            query_start = datetime.fromisoformat(start_str)
        except (ValueError, TypeError):
            query_start = now
    else:
        query_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    query_end = query_start + timedelta(days=1)
    events = (
        db.query(Event)
        .filter(
            Event.status != "cancelled",
            Event.start_time < query_end,
            Event.end_time > query_start,
        )
        .order_by(Event.start_time)
        .all()
    )

    if not events:
        date_str = query_start.strftime("%m月%d日")
        return f"{date_str}没有日程安排。", None

    lines = []
    for e in events:
        t = e.start_time.strftime("%H:%M")
        lines.append(f"• {t} {e.title}")
    return "您的日程如下：\n" + "\n".join(lines), {"type": "query_result", "events": [{"id": e.id, "title": e.title} for e in events]}


async def _handle_update_event(intent: dict, db: Session) -> tuple[str, dict | None]:
    """Update an existing event from parsed intent — find by title/time, then apply changes."""
    title_hint = intent.get("title", "")
    start_str = intent.get("start_time")
    new_title = intent.get("new_title") or title_hint
    new_location = intent.get("location", "")
    new_description = intent.get("description", "")

    if not title_hint and not start_str:
        return '请问要修改哪个日程呢？你可以说「把XX改到明天下午」或「修改XX的时间」。', None

    # Build query — prefer time-based matching
    query = db.query(Event).filter(Event.status != "cancelled")

    target_time = None
    if start_str:
        try:
            target_time = datetime.fromisoformat(start_str)
        except (ValueError, TypeError):
            target_time = None

    if target_time:
        # Find events within ±1 hour of the given time
        window_start = target_time - timedelta(hours=1)
        window_end = target_time + timedelta(hours=1)
        query = query.filter(
            Event.start_time >= window_start,
            Event.start_time <= window_end,
        )
    if title_hint:
        query = query.filter(Event.title.contains(title_hint))

    candidates = query.order_by(Event.start_time).all()

    # Fallback: title-only search if time-based + title returned nothing
    if not candidates and target_time and title_hint:
        candidates = (
            db.query(Event)
            .filter(
                Event.status != "cancelled",
                Event.title.contains(title_hint),
            )
            .order_by(Event.start_time)
            .all()
        )

    if not candidates:
        desc = title_hint or start_str or "该"
        return f"没有找到与「{desc}」相关的日程。", None

    # If multiple matches and the user provided a time, try to pick the closest future one
    if len(candidates) > 1 and target_time and start_str:
        # If the user gave a new time (not just a search time), use title match only
        candidates = [
            e for e in candidates
            if title_hint and title_hint in e.title
        ] or candidates

    if len(candidates) > 1:
        lines = []
        for e in candidates[:5]:
            t = e.start_time.strftime("%m月%d日 %H:%M")
            lines.append(f"• {t} {e.title}")
        return (
            f"找到多个匹配日程：\n" + "\n".join(lines) + "\n请指明要修改哪一个。"
        ), {"type": "update_ambiguous", "candidates": [{"id": e.id, "title": e.title, "start_time": e.start_time.isoformat()} for e in candidates]}

    event = candidates[0]

    # Apply changes
    changes = []
    if new_title and new_title != event.title:
        event.title = new_title
        changes.append(f"标题改为「{new_title}」")

    if start_str:
        try:
            new_start = datetime.fromisoformat(start_str)
            old_duration = event.end_time - event.start_time
            new_end = new_start + old_duration
            event.start_time = new_start
            event.end_time = new_end
            changes.append(f"时间改为{new_start.strftime('%m月%d日 %H:%M')}")
        except (ValueError, TypeError):
            pass

    if new_location:
        event.location = new_location
        changes.append(f"地点改为{new_location}")

    if new_description:
        event.description = new_description
        changes.append("更新了备注")

    if not changes:
        return (
            f"「{event.title}」的哪些信息需要修改呢？可以改时间、地点或标题。"
        ), None

    event.updated_at = datetime.now()
    db.commit()
    db.refresh(event)

    reply = f"已更新日程「{event.title}」：{'，'.join(changes)}。"
    reminder_service.delete_for_event(db, event.id)
    reminder_service.create_for_event(db, event, advance_minutes=15)

    return reply, {"type": "event_updated", "event_id": event.id}


def _handle_delete_event(intent: dict, db: Session) -> tuple[str, dict | None]:
    title = intent.get("title", "")
    start_str = intent.get("start_time")

    # If no title and no time, ask
    if not title and not start_str:
        return "请问要删除哪个日程？", None

    # Build query — prefer time match over title match
    query = db.query(Event).filter(Event.status != "cancelled")

    if start_str:
        try:
            target_time = datetime.fromisoformat(start_str)
        except (ValueError, TypeError):
            target_time = None
    else:
        target_time = None

    if target_time:
        # Match events within ±30 min of the given time
        window_start = target_time - timedelta(minutes=30)
        window_end = target_time + timedelta(minutes=30)
        query = query.filter(
            Event.start_time >= window_start,
            Event.start_time <= window_end,
        )
    elif title:
        query = query.filter(Event.title.contains(title))

    events = query.order_by(Event.start_time).all()

    # If time query returns nothing, fall back to title search
    if not events and target_time and title:
        events = (
            db.query(Event)
            .filter(
                Event.status != "cancelled",
                Event.title.contains(title),
            )
            .order_by(Event.start_time)
            .all()
        )

    if not events:
        desc = title or start_str or "该"
        return f"没有找到与「{desc}」相关的日程。", None

    if len(events) == 1:
        reminder_service.delete_for_event(db, events[0].id)
        db.delete(events[0])
        db.commit()
        return f"已删除日程「{events[0].title}」。", {"type": "event_deleted", "event_id": events[0].id}

    # Multiple matches — list them with times
    lines = []
    for e in events[:5]:
        t = e.start_time.strftime("%H:%M")
        lines.append(f"• {t} {e.title}")
    return f"找到多个匹配的日程：\n" + "\n".join(lines) + "\n请确认要删除哪一个？", None


async def _handle_set_reminder(intent: dict, db: Session) -> tuple[str, dict | None]:
    """Set a reminder — either for an existing event or a standalone reminder."""
    title = intent.get("title", "")
    event_id = intent.get("event_id")
    advance_minutes = intent.get("advance_minutes", 15)
    remind_type = intent.get("remind_type", "popup")

    # If event_id is given, attach reminder to that event
    if event_id:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return "未找到该日程。", None
        reminder = reminder_service.create_for_event(
            db, event, advance_minutes=advance_minutes, remind_type=remind_type
        )
        return (
            f"已为「{event.title}」设置提前{advance_minutes}分钟的提醒。"
        ), {"type": "reminder_created", "reminder_id": reminder.id}

    # If title is given, find matching event
    if title:
        events = db.query(Event).filter(
            Event.title.contains(title),
            Event.status != "cancelled",
        ).order_by(Event.start_time).all()
        if events:
            event = events[0]
            reminder = reminder_service.create_for_event(
                db, event, advance_minutes=advance_minutes, remind_type=remind_type
            )
            return (
                f"已为「{event.title}」设置提前{advance_minutes}分钟的提醒。"
            ), {"type": "reminder_created", "reminder_id": reminder.id}

    # Standalone reminder: extract time from intent
    start_str = intent.get("start_time")
    if start_str:
        try:
            remind_at = datetime.fromisoformat(start_str)
        except (ValueError, TypeError):
            remind_at = datetime.now() + timedelta(minutes=advance_minutes)
    else:
        remind_at = datetime.now() + timedelta(minutes=advance_minutes)

    standalone = Reminder(
        title=title or "提醒事项",
        remind_at=remind_at,
        remind_type=remind_type,
        advance_minutes=advance_minutes,
        message=intent.get("description", "") or title or "提醒事项",
    )
    db.add(standalone)
    db.commit()
    db.refresh(standalone)

    time_str = remind_at.strftime("%m月%d日 %H:%M")
    return (
        f"已设置提醒「{standalone.title}」，时间：{time_str}。"
    ), {"type": "reminder_created", "reminder_id": standalone.id}


def _handle_auto_schedule(intent: dict, db: Session) -> tuple[str, dict | None]:
    """Auto-schedule tasks into free slots."""
    task_descriptions = intent.get("tasks", [])
    if not task_descriptions:
        return "请告诉我您需要安排哪些事项。", None

    tasks = []
    for desc in task_descriptions:
        desc = desc.strip()
        if not desc:
            continue
        task = PendingTask(
            title=desc,
            estimated_duration_minutes=60,
            priority=0,
        )
        db.add(task)
        tasks.append(task)

    if not tasks:
        return "请告诉我您需要安排哪些事项。", None

    scheduled, unscheduled = scheduler.auto_schedule_week(db, tasks)
    db.commit()

    msg = f"已为您自动安排{len(scheduled)}个事项"
    if unscheduled:
        msg += f"，{len(unscheduled)}个事项未能安排：{'、'.join(unscheduled)}"
    return msg, {
        "type": "auto_scheduled",
        "scheduled_count": len(scheduled),
        "unscheduled": unscheduled,
    }


async def _handle_commute_followup(event_id: str, db: Session) -> tuple[str, dict | None]:
    """Handle user confirming they want commute time calculation."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.location:
        return "好的，不过这个日程没有设置地点，无法计算通勤时间。", None

    # Default to "家" as origin — in production this would come from user preferences
    origin = "家"
    suggestion = await map_service.suggest_commute_reminder(
        origin=origin,
        event_title=event.title,
        event_start=event.start_time,
        event_location=event.location,
    )

    # Create commute reminder
    reminder = reminder_service.create_commute_reminder(
        db,
        event=event,
        origin=origin,
        commute_minutes=suggestion["commute_minutes"],
    )

    reply = (
        f"{suggestion['message']}\n"
        f"已为您设置出发提醒，将在{reminder.remind_at.strftime('%H:%M')}通知您。"
    )
    return reply, {
        "type": "commute_reminder_created",
        "reminder_id": reminder.id,
        "commute_info": suggestion,
    }


def _handle_chat(intent: dict, state) -> str:
    """Handle general chat / greetings."""
    text = intent.get("title", "") or ""
    if any(kw in text for kw in ["你好", "嗨", "hello", "hi"]):
        return "你好！我是您的智能语音日程管家，有什么可以帮您安排的？"
    if any(kw in text for kw in ["谢谢", "感谢", "thanks"]):
        return "不客气！随时为您服务。"
    return "请问我能帮您做些什么？比如创建日程、查看今天的安排，或者帮您自动规划一周计划。"
