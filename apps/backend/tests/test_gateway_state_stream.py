from types import SimpleNamespace

from app.mesh.gateway import MeshGateway


def _mk_gateway() -> MeshGateway:
    return MeshGateway(
        port="COM_TEST",
        baudrate=115200,
        channel_name="#i2c-am2301",
        channel_idx=1,
        actuator_name="Rtp-02-switch",
    )


def _mk_event(text: str, channel_idx: int = 1):
    return SimpleNamespace(payload={"channel_idx": channel_idx, "text": text})


def test_subscriber_receives_snapshot_on_state_update():
    gw = _mk_gateway()
    q = gw.subscribe_state()

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b10000000"))

    snapshot = q.get_nowait()
    assert snapshot["0"]["state"] == "ON"
    assert all(snapshot[str(p)]["state"] == "OFF" for p in range(1, 8))


def test_late_subscriber_gets_nothing_until_next_message():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b11111111"))

    q = gw.subscribe_state()
    assert q.empty()  # no history replay — that's the route's job on connect

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))
    snapshot = q.get_nowait()
    assert snapshot["0"]["state"] == "OFF"


def test_unsubscribed_queue_receives_nothing_further():
    gw = _mk_gateway()
    q = gw.subscribe_state()
    gw.unsubscribe_state(q)

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b11111111"))

    assert q.empty()


def test_slow_subscriber_keeps_only_latest_snapshot_not_a_backlog():
    # maxsize=1 by design (see MeshGateway.subscribe_state): a consumer that
    # falls behind should skip straight to the newest state, never build up
    # a queue of stale intermediate ones.
    gw = _mk_gateway()
    q = gw.subscribe_state()

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b10000000"))
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b01000000"))
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))

    assert q.qsize() == 1
    snapshot = q.get_nowait()
    assert all(s["state"] == "OFF" for s in snapshot.values())
    assert q.empty()


def test_multiple_subscribers_all_receive_the_same_update():
    gw = _mk_gateway()
    q1 = gw.subscribe_state()
    q2 = gw.subscribe_state()

    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b11111111"))

    assert q1.get_nowait()["0"]["state"] == "ON"
    assert q2.get_nowait()["0"]["state"] == "ON"


def test_snapshot_keys_are_strings_for_json_compat():
    gw = _mk_gateway()
    gw._on_channel_message(_mk_event("Rtp-02-switch: STATE=b00000000"))

    snapshot = gw.actuator_state_snapshot()
    assert set(snapshot.keys()) == {str(p) for p in range(8)}
