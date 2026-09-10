from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Event, new_uuid

Edge = Literal["on", "off"]

MIN_DURATION_SECONDS = 5
DEFAULT_GAP_SECONDS = 15


def _to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def duration_seconds(on_time: time, off_time: time) -> int:
    """Seconds from on_time to off_time, treating off_time <= on_time as
    wrapping past midnight — same convention list_due() already uses for
    interpreting an off_time earlier than on_time."""
    on_s, off_s = _to_seconds(on_time), _to_seconds(off_time)
    return (off_s - on_s) if off_s > on_s else (off_s + 86400 - on_s)


def validate_duration(on_time: time, off_time: time) -> None:
    """The single place this rule is enforced — called from both create()
    and update() so the drawer's save path and the drag-drop's move-on-drop
    path can never diverge on it (see UX proposal §05)."""
    duration = duration_seconds(on_time, off_time)
    if duration < MIN_DURATION_SECONDS:
        raise ValueError(
            f"ON/OFF must be at least {MIN_DURATION_SECONDS} seconds apart, got {duration}s"
        )


@dataclass
class EventInput:
    label: str | None
    pin: int
    recurrence: str
    start_date: date
    end_date: date | None
    on_time: object  # datetime.time
    off_time: object  # datetime.time
    enabled: bool
    created_by: str


def create(db: Session, data: EventInput) -> Event:
    validate_duration(data.on_time, data.off_time)
    event = Event(id=new_uuid(), **vars(data))
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_all(db: Session) -> list[Event]:
    return list(db.scalars(select(Event).order_by(Event.start_date, Event.on_time)))


def get_by_id(db: Session, event_id: str) -> Event | None:
    return db.get(Event, event_id)


def update(db: Session, event: Event, data: EventInput) -> Event:
    validate_duration(data.on_time, data.off_time)
    for field, value in vars(data).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


def delete(db: Session, event: Event) -> None:
    db.delete(event)
    db.commit()


def _occurs_on(event: Event, day: date) -> bool:
    if event.recurrence == "once":
        return day == event.start_date
    if event.recurrence == "daily":
        if day < event.start_date:
            return False
        if event.end_date is not None and day > event.end_date:
            return False
        return True
    raise ValueError(f"unknown recurrence: {event.recurrence!r}")


def _trigger_instant(day: date, at) -> datetime:
    return datetime.combine(day, at)


def list_due(db: Session, now: datetime, window: timedelta) -> list[tuple[Event, Edge]]:
    """Events whose ON or OFF instant falls in (now - window, now].

    Stateless by design (§ architecture: no persisted "last fired" column) —
    a missed tick is simply never retried, it just isn't "due" anymore once
    the window has passed. `window` should be >= the scheduler's tick period
    so no instant falls between two ticks unnoticed.
    """
    window_start = now - window
    due: list[tuple[Event, Edge]] = []

    events = list(db.scalars(select(Event).where(Event.enabled.is_(True))))
    for event in events:
        # on_time/off_time are day-local; check both "today" and "yesterday"
        # readings so an off_time past midnight (e.g. on=23:50, off=00:10)
        # is still caught by the correct day's occurrence.
        for day in (now.date(), now.date() - timedelta(days=1)):
            if not _occurs_on(event, day):
                continue

            on_at = _trigger_instant(day, event.on_time)
            if window_start < on_at <= now:
                due.append((event, "on"))

            off_day = day
            off_at = _trigger_instant(off_day, event.off_time)
            if event.off_time <= event.on_time:
                # off_time is on the following calendar day relative to on_time
                off_at += timedelta(days=1)
            if window_start < off_at <= now:
                due.append((event, "off"))

    return due
