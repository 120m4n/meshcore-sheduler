from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    engine = create_engine(url, future=True)

    if url.startswith("sqlite"):
        # WAL lets the scheduler's read tick proceed without blocking on an
        # in-flight API write (and vice versa); irrelevant/no-op on other
        # engines, so it stays sqlite-gated rather than a global pragma.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Session:
    """FastAPI dependency: one session per request, closed after."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
