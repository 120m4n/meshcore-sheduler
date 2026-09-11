import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.mesh.gateway import MeshGateway
from app.repositories import audit_repo, event_repo

logger = logging.getLogger("scheduler.ticker")

TICK_SECONDS = 60
# Slightly wider than the tick interval so a tick that runs a little late
# never lets an instant fall through the gap between two windows.
WINDOW = timedelta(seconds=TICK_SECONDS + 5)

# Active PIN_STATUS refresh: only sent when BOTH the last known state is
# stale AND nothing is about to fire on its own to refresh it for free.
# Keeps a shared LoRa channel from being polled continuously — a channel
# with events happening at least once an hour never needs this at all.
STATE_CHECK_STALE_AFTER = timedelta(minutes=60)
STATE_CHECK_SKIP_IF_EVENT_WITHIN = timedelta(minutes=60)


def _actuator_message(pin: int, edge: str) -> str:
    return f"PIN{pin}_{'ON' if edge == 'on' else 'OFF'}"


def _record_send(session_factory, event, edge: str, message: str, ok: bool, error: str | None) -> None:
    # Own short-lived session, separate from the read session above (already
    # closed by this point) — an audit-write failure must never mask the
    # actual send's own success/failure, so it's isolated in its own
    # try/except rather than reusing the surrounding one.
    db: Session = session_factory()
    try:
        audit_repo.record_event_send(
            db,
            event_id=event.id,
            event_label=event.label,
            pin=event.pin,
            edge=edge,
            message=message,
            ok=ok,
            error=error,
        )
    except Exception:
        logger.exception("failed to write event_sends audit row for event %s", event.id)
    finally:
        db.close()


async def run_tick(session_factory, gateway: MeshGateway, tz: ZoneInfo) -> None:
    db: Session = session_factory()
    try:
        # on_time/off_time are stored and edited as wall-clock times in the
        # single fixed TZ from settings (gap register §8.5) — comparing
        # against datetime.utcnow() here would silently never match outside
        # UTC+0. list_due() itself is timezone-agnostic; it just needs `now`
        # in the same reference frame as the stored times, so this strips
        # tzinfo after localizing rather than passing an aware datetime.
        now_local = datetime.now(tz).replace(tzinfo=None)
        due = event_repo.list_due(db, now_local, WINDOW)
        next_at = event_repo.next_instant(db, now_local)
    finally:
        db.close()

    for event, edge in due:
        msg = _actuator_message(event.pin, edge)
        ok = True
        error: str | None = None
        try:
            # send_channel is fire-and-forget: success here means the
            # companion accepted the packet for transmission, nothing more.
            # The actuator's echo (if/when it arrives) updates
            # gateway.get_actuator_state(pin) independently, on its own
            # schedule — it is NOT awaited or correlated to this send. See
            # app/mesh/gateway.py module docstring for why: channel
            # broadcasts have no library-level ACK, and the real actuator
            # replies decoupled from the triggering command.
            await gateway.send_channel(msg)
            logger.info("fired %s for event %s (%s)", msg, event.id, event.label or "unlabeled")
        except Exception as exc:
            ok = False
            error = str(exc)
            logger.exception("failed to fire %s for event %s — no catch-up, next tick moves on", msg, event.id)

        _record_send(session_factory, event, edge, msg, ok, error)

    await _maybe_refresh_actuator_state(gateway, next_at, now_local)


async def _maybe_refresh_actuator_state(
    gateway: MeshGateway, next_at: datetime | None, now_local: datetime
) -> None:
    """Actively refresh actuator_state via PIN_STATUS only when the last
    known reading is stale AND nothing scheduled will refresh it for free
    within STATE_CHECK_SKIP_IF_EVENT_WITHIN — an event about to fire
    already produces a real echo, so forcing a check too is redundant load
    on a shared LoRa channel."""
    last_check = gateway.last_state_check_at
    if last_check is not None:
        stale_for = time.monotonic() - last_check
        if stale_for < STATE_CHECK_STALE_AFTER.total_seconds():
            return

    if next_at is not None and (next_at - now_local) < STATE_CHECK_SKIP_IF_EVENT_WITHIN:
        return

    try:
        await gateway.request_pin_status()
        logger.info("sent active PIN_STATUS refresh (stale actuator_state, no event due soon)")
    except Exception:
        logger.exception("active PIN_STATUS refresh failed")


def start_scheduler(session_factory, gateway: MeshGateway, tz: ZoneInfo) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_tick,
        "interval",
        seconds=TICK_SECONDS,
        args=[session_factory, gateway, tz],
        id="mesh-event-ticker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("scheduler started, tick every %ds", TICK_SECONDS)
    return scheduler
