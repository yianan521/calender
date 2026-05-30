"""SQLAlchemy database setup."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call at application startup."""
    # Ensure all models are imported before creating tables
    from .models.event import Event, PendingTask  # noqa: F401
    from .models.dialogue import DialogueSession, DialogueMessage  # noqa: F401
    from .models.reminder import Reminder  # noqa: F401
    Base.metadata.create_all(bind=engine)
