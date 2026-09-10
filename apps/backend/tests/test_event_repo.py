from datetime import date, datetime, time, timedelta

import pytest

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


def test_off_time_crossing_midnight_is_rejected(db):
    # Events can no longer cross midnight — off_time must be strictly after
    # on_time, same day. Split into two events instead.
    with pytest.raises(ValueError, match="OFF time must be after ON time"):
        _mk(
            db,
            recurrence="daily",
            start_date=date(2026, 1, 1),
            end_date=None,
            on_time=time(23, 50),
            off_time=time(0, 10),
        )


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


def test_next_instant_none_when_no_events(db):
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) is None


def test_next_instant_returns_todays_upcoming_on(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(14, 0), off_time=time(15, 0))
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) == datetime(2026, 1, 10, 14, 0)


def test_next_instant_returns_todays_upcoming_off_when_on_already_passed(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(9, 0), off_time=time(15, 0))
    # ON already happened; OFF is still ahead and counts as "next".
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) == datetime(2026, 1, 10, 15, 0)


def test_next_instant_none_for_once_event_fully_in_the_past(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(9, 0), off_time=time(9, 30))
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) is None


def test_next_instant_rolls_daily_event_to_tomorrow(db):
    _mk(db, recurrence="daily", start_date=date(2026, 1, 1), end_date=None, on_time=time(9, 0), off_time=time(9, 30))
    # Today's ON/OFF already passed — the very next instant is tomorrow's ON.
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) == datetime(2026, 1, 11, 9, 0)


def test_next_instant_ignores_disabled_events(db):
    _mk(db, recurrence="once", start_date=date(2026, 1, 10), on_time=time(14, 0), off_time=time(15, 0), enabled=False)
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) is None


def test_next_instant_picks_soonest_across_multiple_events(db):
    _mk(db, pin=1, recurrence="once", start_date=date(2026, 1, 10), on_time=time(18, 0), off_time=time(19, 0))
    _mk(db, pin=2, recurrence="once", start_date=date(2026, 1, 10), on_time=time(12, 0), off_time=time(13, 0))
    assert event_repo.next_instant(db, datetime(2026, 1, 10, 10, 0, 0)) == datetime(2026, 1, 10, 12, 0)
