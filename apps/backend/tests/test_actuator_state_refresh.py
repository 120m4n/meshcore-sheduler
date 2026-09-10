import asyncio
import time
from datetime import datetime, timedelta

from app.scheduler.ticker import (
    STATE_CHECK_SKIP_IF_EVENT_WITHIN,
    STATE_CHECK_STALE_AFTER,
    _maybe_refresh_actuator_state,
)

NOW = datetime(2026, 1, 10, 12, 0, 0)


class _StubGateway:
    def __init__(self, last_state_check_at: float | None):
        self.last_state_check_at = last_state_check_at
        self.requested = False

    async def request_pin_status(self) -> None:
        self.requested = True


def test_skips_when_last_check_is_recent_even_if_next_event_is_far():
    gw = _StubGateway(last_state_check_at=time.monotonic())  # just checked
    next_at = NOW + timedelta(hours=5)  # nothing coming up soon either way
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at, NOW))
    assert gw.requested is False


def test_skips_when_next_event_is_soon_even_if_last_check_is_stale():
    stale_at = time.monotonic() - (STATE_CHECK_STALE_AFTER.total_seconds() + 60)
    gw = _StubGateway(last_state_check_at=stale_at)
    next_at = NOW + timedelta(minutes=5)  # about to fire on its own
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at, NOW))
    assert gw.requested is False


def test_refreshes_when_both_stale_and_nothing_due_soon():
    stale_at = time.monotonic() - (STATE_CHECK_STALE_AFTER.total_seconds() + 60)
    gw = _StubGateway(last_state_check_at=stale_at)
    next_at = NOW + timedelta(hours=5)
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at, NOW))
    assert gw.requested is True


def test_refreshes_when_stale_and_no_events_scheduled_at_all():
    stale_at = time.monotonic() - (STATE_CHECK_STALE_AFTER.total_seconds() + 60)
    gw = _StubGateway(last_state_check_at=stale_at)
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at=None, now_local=NOW))
    assert gw.requested is True


def test_refreshes_when_never_checked_and_nothing_due_soon():
    gw = _StubGateway(last_state_check_at=None)
    next_at = NOW + timedelta(hours=5)
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at, NOW))
    assert gw.requested is True


def test_exactly_at_skip_threshold_still_refreshes():
    # next_at - now_local == STATE_CHECK_SKIP_IF_EVENT_WITHIN exactly: the
    # comparison is strict "<", so exactly-at-threshold does not count as
    # "within" — documents the boundary rather than asserting either way is
    # inherently "correct".
    stale_at = time.monotonic() - (STATE_CHECK_STALE_AFTER.total_seconds() + 60)
    gw = _StubGateway(last_state_check_at=stale_at)
    next_at = NOW + STATE_CHECK_SKIP_IF_EVENT_WITHIN
    asyncio.run(_maybe_refresh_actuator_state(gw, next_at, NOW))
    assert gw.requested is True
