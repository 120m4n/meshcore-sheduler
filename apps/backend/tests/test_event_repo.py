from datetime import date, datetime, time, timedelta

from app.repositories import event_repo
from app.repositories.event_repo import EventInput


def _mk(db, **overrides):
    defaults = dict(
        label="t",
        pin=1,
        recurrence="once",
        start_date=date(2026, 1, 10),
        end_date=None,
        on_time=time(10, 0),
        off_time=time(11, 0),
        enabled=True,
        created_by="tester",
    )
    defaults.update(overrides)
    return event_repo.create(db, EventInput(**defaults))


WINDOW = timedelta(seconds=65)


def test_once_fires_on_exact_on_time(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(10, 0), off_time=time(11, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 10, 10, 0, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due] == [(1, "on")]


def test_once_fires_on_exact_off_time(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(10, 0), off_time=time(11, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 10, 11, 0, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due] == [(1, "off")]


def test_once_does_not_fire_on_other_days(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(10, 0), off_time=time(11, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 11, 10, 0, 0), WINDOW)
    assert due == []


def test_once_does_not_fire_outside_window(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(10, 0), off_time=time(11, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 10, 10, 5, 0), WINDOW)
    assert due == []


def test_daily_before_start_date_does_not_fire(db):
    _mk(db, recurrence="daily", start_date=date(2026, 1, 10), end_date=None, on_time=time(9, 0), off_time=time(17, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 5, 9, 0, 0), WINDOW)
    assert due == []


def test_daily_after_end_date_does_not_fire(db):
    _mk(
        db,
        recurrence="daily",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        on_time=time(9, 0),
        off_time=time(17, 0),
    )
    due = event_repo.list_due(db, datetime(2026, 1, 15, 9, 0, 0), WINDOW)
    assert due == []


def test_daily_fires_every_day_in_range(db):
    _mk(
        db,
        recurrence="daily",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        on_time=time(9, 0),
        off_time=time(17, 0),
    )
    due = event_repo.list_due(db, datetime(2026, 1, 15, 9, 0, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due] == [(1, "on")]


def test_daily_unbounded_end_date_still_fires(db):
    _mk(db, recurrence="daily", start_date=date(2026, 1, 1), end_date=None, on_time=time(9, 0), off_time=time(17, 0))
    due = event_repo.list_due(db, datetime(2027, 6, 1, 9, 0, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due] == [(1, "on")]


def test_off_time_crossing_midnight_fires_next_day(db):
    # on at 23:50 day N, off at 00:10 -> off belongs to day N+1's occurrence
    _mk(
        db,
        recurrence="daily",
        start_date=date(2026, 1, 1),
        end_date=None,
        on_time=time(23, 50),
        off_time=time(0, 10),
    )
    due_on = event_repo.list_due(db, datetime(2026, 1, 5, 23, 50, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due_on] == [(1, "on")]

    due_off = event_repo.list_due(db, datetime(2026, 1, 6, 0, 10, 0), WINDOW)
    assert [(e.pin, edge) for e, edge in due_off] == [(1, "off")]


def test_disabled_event_never_fires(db):
    _mk(db, recurrence="daily", start_date=date(2026, 1, 1), end_date=None, enabled=False)
    due = event_repo.list_due(db, datetime(2026, 1, 15, 10, 0, 0), WINDOW)
    assert due == []


def test_missed_tick_is_not_retroactively_fired(db):
    """No catch-up by design: once `now` has moved past window_start for an
    instant, that instant is simply gone, not queued for the next check."""
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(10, 0), off_time=time(11, 0))
    due = event_repo.list_due(db, datetime(2026, 1, 10, 10, 30, 0), WINDOW)
    assert due == []
