from datetime import date, time

import pytest

from app.repositories import event_repo
from app.repositories.event_repo import EventInput


def _mk_input(**overrides):
    defaults = dict(
        label="t",
        pin=0,
        recurrence="once",
        start_date=date(2026, 1, 10),
        end_date=None,
        on_time=time(10, 0, 0),
        off_time=time(11, 0, 0),
        enabled=True,
        created_by="tester",
    )
    defaults.update(overrides)
    return EventInput(**defaults)


def test_create_rejects_overlap_same_pin_same_day(db):
    event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(11, 0, 0)))
    with pytest.raises(ValueError, match="Overlaps with existing event on pin 0"):
        event_repo.create(db, _mk_input(on_time=time(10, 30, 0), off_time=time(11, 30, 0)))


def test_create_allows_overlap_on_different_pin(db):
    event_repo.create(db, _mk_input(pin=0, on_time=time(10, 0, 0), off_time=time(11, 0, 0)))
    # Same time window, different pin — independent physical channels, not a conflict.
    event = event_repo.create(db, _mk_input(pin=1, on_time=time(10, 0, 0), off_time=time(11, 0, 0)))
    assert event.id


def test_create_allows_events_touching_edges(db):
    event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(11, 0, 0)))
    # B starts exactly when A ends — chained, not overlapping.
    event = event_repo.create(db, _mk_input(on_time=time(11, 0, 0), off_time=time(12, 0, 0)))
    assert event.id


def test_create_rejects_overlap_with_daily_event(db):
    event_repo.create(
        db,
        _mk_input(
            recurrence="daily",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            on_time=time(9, 0, 0),
            off_time=time(17, 0, 0),
        ),
    )
    # A "once" event on a day within the daily event's range, same pin, overlapping hours.
    with pytest.raises(ValueError, match="Overlaps with existing event on pin 0"):
        event_repo.create(db, _mk_input(recurrence="once", start_date=date(2026, 1, 15), on_time=time(10, 0, 0), off_time=time(10, 30, 0)))


def test_create_allows_once_event_outside_daily_range(db):
    event_repo.create(
        db,
        _mk_input(
            recurrence="daily",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 10),
            on_time=time(9, 0, 0),
            off_time=time(17, 0, 0),
        ),
    )
    # Same hours, same pin, but the once event's day is after the daily range ends.
    event = event_repo.create(
        db, _mk_input(recurrence="once", start_date=date(2026, 1, 15), on_time=time(9, 0, 0), off_time=time(17, 0, 0))
    )
    assert event.id


def test_create_rejects_overlap_two_daily_events_unbounded(db):
    event_repo.create(
        db,
        _mk_input(recurrence="daily", start_date=date(2026, 1, 1), end_date=None, on_time=time(9, 0, 0), off_time=time(17, 0, 0)),
    )
    with pytest.raises(ValueError, match="Overlaps with existing event on pin 0"):
        event_repo.create(
            db,
            _mk_input(recurrence="daily", start_date=date(2026, 6, 1), end_date=None, on_time=time(16, 0, 0), off_time=time(18, 0, 0)),
        )


def test_create_allows_disjoint_daily_ranges_same_hours(db):
    event_repo.create(
        db,
        _mk_input(recurrence="daily", start_date=date(2026, 1, 1), end_date=date(2026, 1, 10), on_time=time(9, 0, 0), off_time=time(17, 0, 0)),
    )
    # Same hours, but the date ranges never overlap.
    event = event_repo.create(
        db,
        _mk_input(recurrence="daily", start_date=date(2026, 1, 11), end_date=None, on_time=time(9, 0, 0), off_time=time(17, 0, 0)),
    )
    assert event.id


def test_create_rejects_overlap_with_disabled_event(db):
    # Disabled events still reserve their slot — enabling one later must not
    # silently create an overlap.
    event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(11, 0, 0), enabled=False))
    with pytest.raises(ValueError, match="Overlaps with existing event on pin 0"):
        event_repo.create(db, _mk_input(on_time=time(10, 30, 0), off_time=time(11, 30, 0)))


def test_update_excludes_self_from_overlap_check(db):
    event = event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(11, 0, 0)))
    # Updating the event's own duration must not conflict with itself.
    updated = event_repo.update(db, event, _mk_input(on_time=time(10, 0, 0), off_time=time(11, 30, 0)))
    assert updated.off_time == time(11, 30, 0)


def test_update_rejects_overlap_with_other_event(db):
    event_repo.create(db, _mk_input(on_time=time(9, 0, 0), off_time=time(10, 0, 0)))
    event_b = event_repo.create(db, _mk_input(on_time=time(11, 0, 0), off_time=time(12, 0, 0)))
    with pytest.raises(ValueError, match="Overlaps with existing event on pin 0"):
        event_repo.update(db, event_b, _mk_input(on_time=time(9, 30, 0), off_time=time(10, 30, 0)))
