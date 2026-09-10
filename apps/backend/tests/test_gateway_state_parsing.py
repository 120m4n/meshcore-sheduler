from types import SimpleNamespace

from app.mesh.gateway import MeshGateway


def _mk_gateway() -> MeshGateway:
    # __init__ touches no hardware — only start() does — so this is safe to
    # construct directly for testing _on_channel_message in isolation.
    return MeshGateway(
        port="COM_TEST",
        baudrate=115200,
        channel_name="#i2c-am2301",
        channel_idx=1,
        actuator_name="Rtp-02-switch",
    )


def _mk_event(text: str, channel_idx: int = 1):
    return SimpleNamespace(payload={"channel_idx": channel_idx, "text": text})


def test_pin_status_response_populates_all_8_pins():
    # Confirmed against real hardware: PIN_STATUS gets answered with no
    # PINn= prefix at all — only the earlier PINn=-anchored regex would have
    # missed this entirely.
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))

    assert len(gw.actuator_states) == 8
    assert all(s.state == "OFF" for s in gw.actuator_states.values())
    assert gw.last_state_check_at is not None


def test_bit_order_matches_hardware_confirmed_mapping():
    # Confirmed against real hardware: PIN3_ON produced
    # "PIN3=ON STATE=b00010000" — most-significant (leftmost) bit is pin 0,
    # descending left to right.
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: PIN3=ON STATE=b00010000"))

    assert gw.get_actuator_state(3).state == "ON"
    for pin in (0, 1, 2, 4, 5, 6, 7):
        assert gw.get_actuator_state(pin).state == "OFF"


def test_echo_with_pinn_prefix_still_parses_full_state():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: PIN0=ON STATE=b10000000"))

    assert gw.get_actuator_state(0).state == "ON"
    assert all(gw.get_actuator_state(p).state == "OFF" for p in range(1, 8))


def test_ignores_messages_from_other_nodes_on_shared_channel():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("SomeOtherNode: STATE=b11111111"))

    assert gw.actuator_states == {}
    assert gw.last_state_check_at is None


def test_ignores_messages_on_a_different_channel_index():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b11111111", channel_idx=99))

    assert gw.actuator_states == {}


def test_ignores_malformed_state_field():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: something unrelated"))

    assert gw.actuator_states == {}


def test_later_state_message_overwrites_earlier_one():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b10000000"))
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))

    assert gw.get_actuator_state(0).state == "OFF"
