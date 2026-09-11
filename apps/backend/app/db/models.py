import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Event(Base):
    """One ON/OFF pair on a PIN. 'once' fires on start_date only; 'daily'
    fires every day in [start_date, end_date] (end_date null = unbounded).
    No last-fired column by design — due-ness is recomputed each tick from
    (recurrence, dates, times), so a restart never needs to "catch up"."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pin: Mapped[int] = mapped_column(Integer, nullable=False)
    recurrence: Mapped[str] = mapped_column(String(16), nullable=False)  # "once" | "daily"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    on_time: Mapped[time] = mapped_column(Time, nullable=False)
    off_time: Mapped[time] = mapped_column(Time, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class EventSend(Base):
    """Audit row for one attempt to fire a scheduled Event onto the mesh
    channel — one per (event, edge) the ticker acted on, success or
    failure. label/pin/edge are snapshotted here rather than read live off
    Event, so the audit trail still reads correctly after the Event is
    edited or deleted (event_id just goes null, see ON DELETE SET NULL)."""

    __tablename__ = "event_sends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    event_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pin: Mapped[int] = mapped_column(Integer, nullable=False)
    edge: Mapped[str] = mapped_column(String(3), nullable=False)  # "on" | "off"
    message: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. "PIN3_ON"
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ActuatorAck(Base):
    """Audit row for every STATE= report the gateway's permanent listener
    observes on the mesh channel, whatever triggered it (RESET, a PINn=ON/
    OFF echo, a PIN_STATUS response, or a third party on the shared
    channel) — see app/mesh/gateway.py's module docstring on why a send and
    its eventual ack are separate, unlinked facts. raw_text keeps the full
    original prefix so the cause is never lost even though it isn't
    modeled as its own column."""

    __tablename__ = "actuator_acks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    node: Mapped[str] = mapped_column(String(100), nullable=False)
    state_bits: Mapped[str] = mapped_column(String(8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class OtpChallenge(Base):
    """A single pending OTP tied to a not-yet-authenticated session cookie."""

    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user: Mapped[str] = mapped_column(String(100), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
