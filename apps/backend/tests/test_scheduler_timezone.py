from datetime import datetime, time, date
from zoneinfo import ZoneInfo

from app.repositories import event_repo
from app.repositories.event_repo import EventInput


def test_run_tick_uses_configured_tz_not_utc(db, monkeypatch):
    """Regression test: run_tick() must compare against wall-clock time in
    the configured TZ, not datetime.utcnow(). on_time/off_time are stored
    and edited as local time (gap register §8.5) — comparing against UTC
    means the scheduler never fires outside UTC+0, discovered via a live
    end-to-end test against real hardware where a UTC-5 machine's events
    silently never triggered."""
    from app.scheduler.ticker import run_tick

    tz = ZoneInfo("America/Santo_Domingo")  # fixed UTC-4/-5, no DST

    fixed_local = datetime(2026, 6, 15, 10, 0, 0)  # what "now" should resolve to
    fixed_utc_equivalent = datetime(2026, 6, 15, 14, 0, 0)  # UTC-4 offset

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz_arg=None):
            if tz_arg is not None:
                return fixed_local.replace(tzinfo=tz_arg)
            return fixed_local

        @classmethod
        def utcnow(cls):
            return fixed_utc_equivalent

    monkeypatch.setattr("app.scheduler.ticker.datetime", _FrozenDateTime)

    event = event_repo.create(
        db,
        EventInput(
            label="tz test",
            pin=0,
            recurrence="once",
            start_date=date(2026, 6, 15),
            end_date=None,
            on_time=time(10, 0, 0),  # matches fixed_local, NOT fixed_utc_equivalent
            off_time=time(10, 0, 15),
            enabled=True,
            created_by="tester",
        ),
    )

    calls: list[str] = []

    class _StubGateway:
        last_state_check_at = 0.0  # "just checked" — event is 15s away anyway (< 60min skip window)

        async def send_channel(self, msg: str) -> None:
            calls.append(msg)

        async def request_pin_status(self) -> None:
            calls.append("PIN_STATUS")

    import asyncio

    asyncio.run(run_tick(lambda: db, _StubGateway(), tz))

    assert calls == [f"PIN{event.pin}_ON"], (
        "run_tick should have fired using local time (10:00:00), not UTC "
        "(14:00:00) — if this fails, list_due() is being called with "
        "datetime.utcnow() again instead of the configured TZ's wall clock."
    )
