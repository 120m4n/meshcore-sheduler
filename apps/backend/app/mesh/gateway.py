import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from meshcore import EventType, MeshCore

from app.mesh.channel_bootstrap import ensure_channel
from app.repositories import audit_repo

logger = logging.getLogger("mesh.gateway")

T = TypeVar("T")

# Channel messages (send_chan_msg) are broadcast/flood — the library only
# gives expected_ack/EventType.ACK for unicast send_msg/send_cmd to a single
# contact, so there's no request/response primitive for a channel command.
# Confirmed against real hardware: the actuator on #i2c-am2301 answers
# PINx_ON/OFF with a text echo on the same channel — but decoupled, on its
# own schedule, e.g. "Rtp-02-switch: PIN0=ON STATE=b10000000" arriving some
# time after the send, not correlated 1:1 to a specific send call. So this
# gateway does NOT try to match "this echo answers that send" — it runs a
# permanent background listener that keeps the last-observed state, and
# callers read that state independently of when/whether they sent anything.
# "The command went out" (send_channel succeeded) and "the actuator's
# reported state reflects it" are two separate, unlinked facts.
#
# The channel is shared — other nodes/companions can also send PINx_ON/OFF
# or PIN_STATUS to this same actuator, and it always answers with its full
# STATE=b<8 bits> snapshot regardless of who asked or what triggered it.
# That field, not the PINn= prefix (which is absent from a PIN_STATUS
# response — confirmed against real hardware: "Rtp-02-switch:
# STATE=b00000000"), is the only real source of truth for all 8 pins at
# once. Bit order confirmed against hardware too: PIN3_ON produced
# "PIN3=ON STATE=b00010000" — the most-significant bit (leftmost, index 0)
# is pin 0, descending left to right.
#
# The `.*` between "node:" and "STATE=b" is deliberately unconstrained — the
# actuator prefixes STATE= with whatever triggered it (nothing for
# PIN_STATUS, "PINn=ON"/"PINn=OFF" for a command echo, "RESET" after a power
# cycle, ...) and this parser doesn't care which, it only needs the trailing
# 8-bit snapshot. Likewise nothing after the bits is required, so a suffix
# like "(auto-off 3m)" is silently ignored. Do not narrow this to a specific
# prefix — see test_gateway_state_parsing.py for the prefix variants this
# must keep matching.
_STATE_RE = re.compile(r"^(?P<node>[^:]+):.*\bSTATE=b(?P<bits>[01]{8})\b")


@dataclass
class ActuatorState:
    pin: int
    state: str  # "ON" | "OFF"
    raw: str
    observed_at: float  # time.monotonic()


@dataclass
class _Job:
    coro: Callable[[MeshCore], Awaitable[object]]
    future: "asyncio.Future[object]"


class MeshGateway:
    """Owns the single serial connection to the companion for the whole
    process lifetime. Every send — OTP delivery, scheduler firing, anything
    added later — goes through submit()/send_channel(), which serialize onto
    one asyncio.Queue worked by one coroutine. This is what prevents two
    callers from opening/racing the same USB port (see architecture doc,
    "conexion efimera" discussion): there is only ever one open() for the
    life of the process, and callers only ever queue a command on top of it.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        channel_name: str,
        channel_idx: int,
        actuator_name: str,
        session_factory: Callable[[], object] | None = None,
    ):
        self._port = port
        self._baudrate = baudrate
        self._channel_name = channel_name
        self._channel_idx = channel_idx
        self._actuator_name = actuator_name
        # Optional so existing/unit tests that only exercise parsing and
        # pub/sub (no DB involved) can keep constructing a gateway with no
        # session factory at all — see test_gateway_state_parsing.py /
        # test_gateway_state_stream.py. Production always passes one (see
        # app/main.py).
        self._session_factory = session_factory
        self._mc: MeshCore | None = None
        self._queue: asyncio.Queue[_Job] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._echo_subscription = None
        self._actuator_state: dict[int, ActuatorState] = {}
        # Set once per STATE= message (all 8 pins update together from one
        # message), not per pin — see _on_channel_message.
        self._last_state_check_at: float | None = None
        # Real-time push targets (see subscribe_state/_broadcast_state) —
        # the /actuator-state/stream route is the only thing that reads
        # these. The frontend NEVER talks to the mesh channel directly or
        # indirectly (no "refresh" action triggers a send here); it only
        # ever receives whatever this gateway already has in memory.
        self._subscribers: set["asyncio.Queue[dict]"] = set()

    async def start(self) -> None:
        self._mc = await MeshCore.create_serial(
            self._port, self._baudrate, auto_reconnect=True
        )
        if self._mc is None:
            raise RuntimeError(
                f"companion not reachable on serial port {self._port!r} "
                "(check MESH_SERIAL_PORT and that no other process holds it)"
            )
        await ensure_channel(self._mc, self._channel_name, self._channel_idx)
        self._worker_task = asyncio.create_task(self._worker(), name="mesh-gateway-worker")

        # Permanent listener: keeps last-known actuator state per PIN,
        # independent of anything this process sends. Requires
        # start_auto_message_fetching so incoming channel messages actually
        # get pulled off the companion and dispatched as CHANNEL_MSG_RECV
        # events rather than sitting unread.
        await self._mc.start_auto_message_fetching()
        self._echo_subscription = self._mc.subscribe(
            EventType.CHANNEL_MSG_RECV, self._on_channel_message
        )

        logger.info("mesh gateway started on %s", self._port)

        # Prime actuator_state with a real reading right away instead of
        # leaving it empty until some other node happens to trigger an echo.
        try:
            await self.request_pin_status()
        except Exception:
            logger.exception("initial PIN_STATUS request failed — actuator_state starts empty")

    async def stop(self) -> None:
        if self._echo_subscription is not None:
            self._echo_subscription.unsubscribe()
            self._echo_subscription = None
        if self._worker_task is not None:
            self._worker_task.cancel()
            self._worker_task = None
        if self._mc is not None:
            await self._mc.stop_auto_message_fetching()
            await self._mc.disconnect()
            self._mc = None
        logger.info("mesh gateway stopped")

    def _on_channel_message(self, event) -> None:
        payload = event.payload
        if payload.get("channel_idx") != self._channel_idx:
            return
        text = payload.get("text", "")
        m = _STATE_RE.match(text)
        if not m:
            return
        # Other nodes may share this channel — only trust state reports
        # attributed to the configured actuator's node name.
        if m.group("node") != self._actuator_name:
            return
        now = time.monotonic()
        bits = m.group("bits")
        for pin, bit in enumerate(bits):
            self._actuator_state[pin] = ActuatorState(
                pin=pin, state="ON" if bit == "1" else "OFF", raw=text, observed_at=now
            )
        self._last_state_check_at = now
        logger.info("actuator state update: STATE=b%s (%s)", bits, m.group("node"))
        self._broadcast_state()
        self._record_ack(text, m.group("node"), bits)

    def _record_ack(self, raw_text: str, node: str, bits: str) -> None:
        # Audit trail of every STATE= this gateway ever observed, whatever
        # the cause (RESET, a PINn=ON/OFF echo, a PIN_STATUS response, or a
        # third party on the shared channel) — see ActuatorAck's docstring.
        # A DB hiccup here must never break the live listener (SSE push
        # already happened above via _broadcast_state), so it's isolated.
        if self._session_factory is None:
            return
        db = self._session_factory()
        try:
            audit_repo.record_actuator_ack(db, raw_text=raw_text, node=node, state_bits=bits)
        except Exception:
            logger.exception("failed to write actuator_acks audit row")
        finally:
            db.close()

    def subscribe_state(self) -> "asyncio.Queue[dict]":
        """A new queue that receives this gateway's actuator_state_snapshot()
        every time _on_channel_message observes a STATE= report — the only
        way the real-time stream route learns of a change. maxsize=1: only
        the latest snapshot is ever meaningful, so a consumer that falls
        behind skips straight to the newest one instead of queuing stale
        history (see _broadcast_state)."""
        q: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=1)
        self._subscribers.add(q)
        return q

    def unsubscribe_state(self, q: "asyncio.Queue[dict]") -> None:
        self._subscribers.discard(q)

    def actuator_state_snapshot(self) -> dict[str, dict]:
        """JSON-shaped snapshot of last-observed state per pin, keyed by pin
        number as a string. Single source of truth for how age_seconds is
        computed — both /health and the real-time stream route call this
        rather than each building their own dict, so they can't drift."""
        now = time.monotonic()
        return {
            str(pin): {"state": s.state, "age_seconds": round(now - s.observed_at, 1)}
            for pin, s in self._actuator_state.items()
        }

    def _broadcast_state(self) -> None:
        snapshot = self.actuator_state_snapshot()
        for q in self._subscribers:
            if q.full():
                q.get_nowait()  # drop the stale snapshot, only the latest matters
            q.put_nowait(snapshot)

    def get_actuator_state(self, pin: int) -> ActuatorState | None:
        """Last state this gateway has observed for `pin`, or None if no
        STATE= report has ever been seen. Not correlated to any particular
        send — the actuator reports on its own schedule, and any node on
        the shared channel (not just this process) can trigger one."""
        return self._actuator_state.get(pin)

    @property
    def actuator_states(self) -> dict[int, ActuatorState]:
        """Snapshot of last-observed state for every PIN seen so far. All 8
        pins populate together from a single STATE= message, so in practice
        this is either empty (nothing seen yet) or has all 8 entries."""
        return dict(self._actuator_state)

    @property
    def last_state_check_at(self) -> float | None:
        """time.monotonic() of the most recent STATE= message (echo or
        PIN_STATUS response), or None if none has been seen yet."""
        return self._last_state_check_at

    async def request_pin_status(self) -> None:
        """Actively ask the actuator to report STATE= right now, rather
        than waiting for an incidental echo. Fire-and-forget like
        send_channel — the response (if/when it arrives) comes back through
        the same permanent listener as any other channel message."""
        await self.send_channel("PIN_STATUS")

    async def _worker(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                assert self._mc is not None
                result = await job.coro(self._mc)
                if not job.future.done():
                    job.future.set_result(result)
            except Exception as exc:  # noqa: BLE001 - propagated to the caller, not swallowed
                logger.exception("mesh job failed")
                if not job.future.done():
                    job.future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def submit(self, coro: Callable[[MeshCore], Awaitable[T]]) -> T:
        loop = asyncio.get_event_loop()
        fut: "asyncio.Future[T]" = loop.create_future()
        await self._queue.put(_Job(coro=coro, future=fut))  # type: ignore[arg-type]
        return await fut

    async def send_channel(self, msg: str) -> object:
        idx = self._channel_idx

        async def _send(mc: MeshCore):
            res = await mc.commands.send_chan_msg(idx, msg)
            if res.is_error():
                raise RuntimeError(f"send_chan_msg failed: {res.payload}")
            return res

        return await self.submit(_send)

    @property
    def is_connected(self) -> bool:
        return self._mc is not None and self._worker_task is not None and not self._worker_task.done()
