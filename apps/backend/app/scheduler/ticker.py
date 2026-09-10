import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.mesh.gateway import MeshGateway
from app.repositories import event_repo

logger = logging.getLogger("scheduler.ticker")

TICK_SECONDS = 60
# Slightly wider than the tick interval so a tick that runs a little late
# never lets an instant fall through the gap between two windows.
WINDOW = timedelta(seconds=TICK_SECONDS + 5)


def _actuator_message(pin: int, edge: str) -> str:
    return f"PIN{pin}_{'ON' if edge == 'on' else 'OFF'}"


async def run_tick(session_factory, gateway: MeshGateway) -> None:
    db: Session = session_factory()
    try:
        due = event_repo.list_due(db, datetime.utcnow(), WINDOW)
    finally:
        db.close()

    for event, edge in due:
        msg = _actuator_message(event.pin, edge)
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
        except Exception:
            logger.exception("failed to fire %s for event %s — no catch-up, next tick moves on", msg, event.id)


def start_scheduler(session_factory, gateway: MeshGateway) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_tick,
        "interval",
        seconds=TICK_SECONDS,
        args=[session_factory, gateway],
        id="mesh-event-ticker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("scheduler started, tick every %ds", TICK_SECONDS)
    return scheduler
