from types import SimpleNamespace

from sqlalchemy import select

from app.db.models import ActuatorAck
from app.mesh.gateway import MeshGateway


def _mk_gateway(session_factory) -> MeshGateway:
    return MeshGateway(
        port="COM_TEST",
        baudrate=115200,
        channel_name="#i2c-am2301",
        channel_idx=1,
        actuator_name="Rtp-02-switch",
        session_factory=session_factory,
    )


def _mk_event(text: str, channel_idx: int = 1):
    return SimpleNamespace(payload={"channel_idx": channel_idx, "text": text})


def test_state_message_writes_an_ack_audit_row(db):
    gw = _mk_gateway(lambda: db)

    gw._on_channel_message(_mk_event("Rtp-02-switch: PIN3=ON STATE=b00010000"))

    rows = list(db.scalars(select(ActuatorAck)))
    assert len(rows) == 1
    assert rows[0].raw_text == "Rtp-02-switch: PIN3=ON STATE=b00010000"
    assert rows[0].node == "Rtp-02-switch"
    assert rows[0].state_bits == "00010000"


def test_reset_and_bare_state_also_get_audited(db):
    # Whatever the cause — see ActuatorAck's docstring — every variant this
    # gateway already knows how to parse (test_gateway_state_parsing.py)
    # must also land in the audit trail.
    gw = _mk_gateway(lambda: db)

    gw._on_channel_message(_mk_event("Rtp-02-switch: RESET STATE=b00000000"))
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b11111111"))

    rows = list(db.scalars(select(ActuatorAck).order_by(ActuatorAck.observed_at)))
    assert len(rows) == 2
    assert rows[0].raw_text == "Rtp-02-switch: RESET STATE=b00000000"
    assert rows[1].raw_text == "Rtp-02-switch: STATE=b11111111"


def test_message_that_fails_to_parse_writes_no_audit_row(db):
    gw = _mk_gateway(lambda: db)

    gw._on_channel_message(_mk_event("Rtp-02-switch: something unrelated"))

    assert list(db.scalars(select(ActuatorAck))) == []


def test_message_from_other_node_writes_no_audit_row(db):
    # Not attributed to the configured actuator — never trusted, never
    # audited either (see test_ignores_messages_from_other_nodes... in
    # test_gateway_state_parsing.py for the same rule on in-memory state).
    gw = _mk_gateway(lambda: db)

    gw._on_channel_message(_mk_event("SomeOtherNode: STATE=b11111111"))

    assert list(db.scalars(select(ActuatorAck))) == []


def test_no_session_factory_skips_audit_without_erroring():
    # Existing parsing/pub-sub tests construct a gateway with no DB at all
    # (session_factory=None default) — must keep working unchanged.
    gw = _mk_gateway(session_factory=None)

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))

    assert gw.get_actuator_state(0).state == "OFF"
