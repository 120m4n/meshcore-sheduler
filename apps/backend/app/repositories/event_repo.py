from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Event, new_uuid

Edge = Literal["on", "off"]

MIN_DURATION_SECONDS = 15
WARN_DURATION_SECONDS = 60 * 60
DEFAULT_GAP_SECONDS = 15


def _to_seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def duration_seconds(on_time: time, off_time: time) -> int:
    """Seconds from on_time to off_time, same calendar day. Events no longer
    cross midnight — off_time must be strictly after on_time (see
    validate_duration); a caller passing off_time <= on_time gets a negative
    or zero result here, which validate_duration rejects."""
    return _to_seconds(off_time) - _to_seconds(on_time)


def validate_duration(on_time: time, off_time: time) -> None:
    """The single place this rule is enforced — called from both create()
    and update() so the drawer's save path and the drag-drop's move-on-drop
    path can never diverge on it (see UX proposal §05).

    OFF must be strictly after ON, same day (no midnight-crossing events —
    split into two events instead), with at least MIN_DURATION_SECONDS
    between them. Durations over WARN_DURATION_SECONDS are allowed but are
    the client's job to flag as a warning, not rejected here."""
    if off_time <= on_time:
        raise ValueError("OFF time must be after ON time (events can't cross midnight)")
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


def _date_range(recurrence: str, start_date: date, end_date: date | None) -> tuple[date, date | None]:
    """(first day, last day or None-for-unbounded) the event occurs on."""
    if recurrence == "once":
        return start_date, start_date
    if recurrence == "daily":
        return start_date, end_date
    raise ValueError(f"unknown recurrence: {recurrence!r}")


def _date_ranges_overlap(
    a_start: date, a_end: date | None, b_start: date, b_end: date | None
) -> bool:
    """True if there's at least one calendar day both ranges cover.
    None as an end date means unbounded (recurs forever)."""
    if a_end is not None and b_start > a_end:
        return False
    if b_end is not None and a_start > b_end:
        return False
    return True


def find_overlap(db: Session, data: EventInput, exclude_id: str | None = None) -> Event | None:
    """First existing event on the same pin whose active date range and
    on/off window overlap this one's, or None.

    Same-pin only — different pins are independent physical channels on the
    actuator, so overlapping schedules on different pins is not a conflict
    (unlike two meetings on one calendar/resource). Touching edges (one
    event's off_time == another's on_time) is allowed — events chain during
    the day, they just can never overlap. exclude_id skips the event being
    updated so it doesn't conflict with its own prior version.

    Disabled events are still checked: enabling one later must not silently
    create an overlap, so the slot is reserved even while off.
    """
    a_start, a_end = _date_range(data.recurrence, data.start_date, data.end_date)

    candidates = db.scalars(select(Event).where(Event.pin == data.pin))
    for other in candidates:
        if exclude_id is not None and other.id == exclude_id:
            continue
        b_start, b_end = _date_range(other.recurrence, other.start_date, other.end_date)
        if not _date_ranges_overlap(a_start, a_end, b_start, b_end):
            continue
        if data.on_time < other.off_time and other.on_time < data.off_time:
            return other
    return None


def _describe(event) -> str:
    label = event.label or f"pin {event.pin}"
    return f"{label} ({event.on_time}–{event.off_time})"


def validate_no_overlap(db: Session, data: EventInput, exclude_id: str | None = None) -> None:
    conflict = find_overlap(db, data, exclude_id)
    if conflict is not None:
        raise ValueError(
            f"Overlaps with existing event on pin {data.pin}: {_describe(conflict)}"
        )


def create(db: Session, data: EventInput) -> Event:
    validate_duration(data.on_time, data.off_time)
    validate_no_overlap(db, data)
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
    validate_no_overlap(db, data, exclude_id=event.id)
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


def _next_instants_for_event(event: Event, now: datetime) -> list[datetime]:
    """This event's ON and/or OFF instants that are still ahead of `now`,
    considering only today and tomorrow — sufficient because a daily event
    repeats every day (if today's are both past, tomorrow's are the very
    next ones) and a once event only ever has one occurrence."""
    instants: list[datetime] = []
    for day in (now.date(), now.date() + timedelta(days=1)):
        if not _occurs_on(event, day):
            continue
        for at in (event.on_time, event.off_time):
            instant = _trigger_instant(day, at)
            if instant > now:
                instants.append(instant)
    return instants


def next_instant(db: Session, now: datetime) -> datetime | None:
    """The single nearest future ON or OFF instant across every enabled
    event (any pin), or None if nothing is scheduled ahead. Used to decide
    whether an active PIN_STATUS check is worth sending — see
    scheduler/ticker.py: no point forcing a mesh round-trip when an event
    about to fire will produce a real echo on its own."""
    candidates: list[datetime] = []
    events = list(db.scalars(select(Event).where(Event.enabled.is_(True))))
    for event in events:
        candidates.extend(_next_instants_for_event(event, now))
    return min(candidates) if candidates else None


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
        # Events no longer cross midnight (validate_duration enforces
        # off_time > on_time, same day), so only "today" needs checking.
        day = now.date()
        if not _occurs_on(event, day):
            continue

        on_at = _trigger_instant(day, event.on_time)
        if window_start < on_at <= now:
            due.append((event, "on"))

        off_at = _trigger_instant(day, event.off_time)
        if window_start < off_at <= now:
            due.append((event, "off"))

    return due
