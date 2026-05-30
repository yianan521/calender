"""AI Voice Scheduler — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import events_router, dialogue_router, schedule_router, tasks_router, reminders_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Voice Scheduler",
    description="智能语音日程管家 — API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(dialogue_router)
app.include_router(schedule_router)
app.include_router(tasks_router)
app.include_router(reminders_router)


@app.get("/")
def root():
    return {"name": "AI Voice Scheduler", "version": "0.1.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
