import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)

    # Matches app/db/engine.py's production pragma — without this, SQLite
    # never enforces FK constraints, so ON DELETE SET NULL (event_sends ->
    # events) would silently no-op in tests while working in production.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
