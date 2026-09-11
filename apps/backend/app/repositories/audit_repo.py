from sqlalchemy.orm import Session

from app.db.models import ActuatorAck, EventSend, new_uuid


def record_event_send(
    db: Session,
    *,
    event_id: str | None,
    event_label: str | None,
    pin: int,
    edge: str,
    message: str,
    ok: bool,
    error: str | None = None,
) -> EventSend:
    row = EventSend(
        id=new_uuid(),
        event_id=event_id,
        event_label=event_label,
        pin=pin,
        edge=edge,
        message=message,
        ok=ok,
        error=error,
    )
    db.add(row)
    db.commit()
    return row


def record_actuator_ack(db: Session, *, raw_text: str, node: str, state_bits: str) -> ActuatorAck:
    row = ActuatorAck(id=new_uuid(), raw_text=raw_text, node=node, state_bits=state_bits)
    db.add(row)
    db.commit()
    return row
