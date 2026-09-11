import asyncio
from datetime import date, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models import EventSend
from app.repositories import event_repo
from app.repositories.event_repo import EventInput
from app.scheduler.ticker import run_tick

TZ = ZoneInfo("America/Bogota")


def _mk_event(db, on_time, off_time, start_date=date(2026, 6, 15)):
    return event_repo.create(
        db,
        EventInput(
            label="audit test",
            pin=2,
            recurrence="once",
            start_date=start_date,
            end_date=None,
            on_time=on_time,
            off_time=off_time,
            enabled=True,
            created_by="tester",
        ),
    )


class _StubGateway:
    last_state_check_at = 0.0

    def __init__(self, fail: bool = False):
        self._fail = fail

    async def send_channel(self, msg: str) -> None:
        if self._fail:
            raise RuntimeError("companion not reachable")

    async def request_pin_status(self) -> None:
        pass


def _freeze(monkeypatch, fixed_local):
    class _FrozenDateTime(type(fixed_local)):
        @classmethod
        def now(cls, tz_arg=None):
            return fixed_local.replace(tzinfo=tz_arg) if tz_arg is not None else fixed_local

    monkeypatch.setattr("app.scheduler.ticker.datetime", _FrozenDateTime)


def test_successful_fire_writes_an_ok_audit_row(db, monkeypatch):
    on_time = time(10, 0, 0)
    event = _mk_event(db, on_time, time(10, 0, 15))
    _freeze(monkeypatch, __import__("datetime").datetime(2026, 6, 15, 10, 0, 0))

    asyncio.run(run_tick(lambda: db, _StubGateway(), TZ))

    rows = list(db.scalars(select(EventSend)))
    assert len(rows) == 1
    assert rows[0].event_id == event.id
    assert rows[0].event_label == "audit test"
    assert rows[0].pin == 2
    assert rows[0].edge == "on"
    assert rows[0].message == "PIN2_ON"
    assert rows[0].ok is True
    assert rows[0].error is None


def test_failed_send_writes_a_not_ok_audit_row_with_error(db, monkeypatch):
    event = _mk_event(db, time(10, 0, 0), time(10, 0, 15))
    _freeze(monkeypatch, __import__("datetime").datetime(2026, 6, 15, 10, 0, 0))

    asyncio.run(run_tick(lambda: db, _StubGateway(fail=True), TZ))

    rows = list(db.scalars(select(EventSend)))
    assert len(rows) == 1
    assert rows[0].event_id == event.id
    assert rows[0].ok is False
    assert "not reachable" in rows[0].error


def test_deleting_the_event_later_keeps_the_audit_row_with_event_id_nulled(db, monkeypatch):
    event = _mk_event(db, time(10, 0, 0), time(10, 0, 15))
    _freeze(monkeypatch, __import__("datetime").datetime(2026, 6, 15, 10, 0, 0))

    asyncio.run(run_tick(lambda: db, _StubGateway(), TZ))
    event_repo.delete(db, event)

    rows = list(db.scalars(select(EventSend)))
    assert len(rows) == 1
    assert rows[0].event_id is None  # ON DELETE SET NULL
    assert rows[0].event_label == "audit test"  # snapshot survives
