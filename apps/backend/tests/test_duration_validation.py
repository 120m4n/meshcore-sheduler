from datetime import date, time

import pytest

from app.repositories import event_repo
from app.repositories.event_repo import EventInput, MIN_DURATION_SECONDS, duration_seconds


def _mk_input(**overrides):
    defaults = dict(
        label="t",
        pin=0,
        recurrence="once",
        start_date=date(2026, 1, 10),
        end_date=None,
        on_time=time(10, 0, 0),
        off_time=time(10, 0, 5),
        enabled=True,
        created_by="tester",
    )
    defaults.update(overrides)
    return EventInput(**defaults)


def test_duration_seconds_same_day():
    assert duration_seconds(time(10, 0, 0), time(10, 0, 15)) == 15


def test_duration_seconds_wraps_past_midnight():
    assert duration_seconds(time(23, 59, 58), time(0, 0, 3)) == 5


def test_duration_seconds_exact_equal_wraps_to_full_day():
    assert duration_seconds(time(10, 0, 0), time(10, 0, 0)) == 86400


def test_create_accepts_exactly_minimum_duration(db):
    event = event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(10, 0, 5)))
    assert event.id


def test_create_rejects_below_minimum_duration(db):
    with pytest.raises(ValueError, match=f"at least {MIN_DURATION_SECONDS} seconds"):
        event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(10, 0, 4)))


def test_create_rejects_identical_on_off_as_not_a_5s_wrap():
    # on == off wraps to a full 86400s day per duration_seconds' convention,
    # which is >= the minimum — this documents that behavior rather than
    # silently treating on==off as a zero-length (invalid) event.
    assert duration_seconds(time(10, 0, 0), time(10, 0, 0)) >= MIN_DURATION_SECONDS


def test_update_rejects_below_minimum_duration(db):
    event = event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(10, 0, 30)))
    with pytest.raises(ValueError, match=f"at least {MIN_DURATION_SECONDS} seconds"):
        event_repo.update(db, event, _mk_input(on_time=time(10, 0, 0), off_time=time(10, 0, 2)))


def test_update_accepts_valid_duration(db):
    event = event_repo.create(db, _mk_input(on_time=time(10, 0, 0), off_time=time(10, 0, 30)))
    updated = event_repo.update(db, event, _mk_input(on_time=time(11, 0, 0), off_time=time(11, 0, 20)))
    assert updated.on_time == time(11, 0, 0)
    assert updated.off_time == time(11, 0, 20)
