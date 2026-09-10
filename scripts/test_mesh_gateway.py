#!/usr/bin/env python3
"""Exercise the backend's MeshGateway against a real companion, without
booting FastAPI/SQLAlchemy/APScheduler.

Confirms: the gateway connects, ensure_channel() finds/keeps the configured
channel, an optional message goes out on it (fire-and-forget), and the
gateway's permanent background listener picks up the actuator's state
reports — the same paths the OTP flow and the scheduler use in production.

The actuator answers PINx_ON/OFF asynchronously and decoupled from any
specific send (confirmed against real hardware) — so this script does NOT
try to match "this echo answers that send". It just starts the gateway
(which starts listening immediately, and sends its own initial PIN_STATUS —
see MeshGateway.start()), optionally fires a command, and prints
gateway.actuator_states over a window so you can see what arrives.

Every response — an echo after PINx_ON/OFF, or a PIN_STATUS reply — carries
the same full STATE=b<8 bits> snapshot of all 8 pins, not just the one
pin mentioned in an echo's PINn= prefix (which PIN_STATUS doesn't even
have — confirmed against real hardware: "Rtp-02-switch: STATE=b00000000").
That field is the gateway's only real source of truth; --pin-status lets
you trigger it directly instead of waiting for an incidental echo.

Usage:
    python scripts/test_mesh_gateway.py -s COM12 [--chan-name '#i2c-am2301']
        [--chan-idx 1] [--actuator-name Rtp-02-switch] [--send "PIN0_ON"]
        [--pin-status] [--listen 15]

Exit 0 on success, 1 on failure.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend"))

from app.mesh.gateway import MeshGateway  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-s", "--serial-port", required=True, help="e.g. COM12 or /dev/ttyUSB0")
    parser.add_argument("-b", "--baudrate", type=int, default=115200)
    parser.add_argument("--chan-name", default="#i2c-am2301")
    parser.add_argument("--chan-idx", type=int, default=1)
    parser.add_argument("--actuator-name", default="Rtp-02-switch", help="node name the listener trusts echoes from")
    parser.add_argument("--send", default=None, help="message to fire-and-forget on the channel (optional)")
    parser.add_argument(
        "--pin-status", action="store_true", help="also actively request a fresh STATE= reading via PIN_STATUS"
    )
    parser.add_argument("--listen", type=float, default=10, help="seconds to watch actuator_states after connecting/sending")
    args = parser.parse_args()

    print(f"Connecting to companion on {args.serial_port} @ {args.baudrate}...")
    gateway = MeshGateway(
        port=args.serial_port,
        baudrate=args.baudrate,
        channel_name=args.chan_name,
        channel_idx=args.chan_idx,
        actuator_name=args.actuator_name,
    )

    try:
        await gateway.start()
    except RuntimeError as e:
        print(f"FAIL: {e}")
        return 1

    print(f"OK: gateway connected, channel {args.chan_name!r} confirmed at idx {args.chan_idx}")
    print(f"Background listener active, trusting state reports from {args.actuator_name!r}")
    if gateway.actuator_states:
        print(f"  (start()'s own initial PIN_STATUS already populated {len(gateway.actuator_states)} pin(s))")

    try:
        if args.send:
            print(f"Sending on channel {args.chan_idx}: {args.send!r} (fire-and-forget, not awaiting any reply)")
            await gateway.send_channel(args.send)
            print("OK: message sent")

        if args.pin_status:
            print("Sending PIN_STATUS (fire-and-forget, not awaiting any reply)...")
            await gateway.request_pin_status()
            print("OK: PIN_STATUS sent")

        if args.listen > 0:
            print(f"Watching actuator_states for {args.listen}s (reports arrive independently)...")
            # All 8 pins update together from one STATE= message (same raw
            # text), so dedupe on raw rather than printing once per pin.
            last_raw: str | None = None
            loop = asyncio.get_event_loop()
            deadline = loop.time() + args.listen
            while loop.time() < deadline:
                states = gateway.actuator_states
                if states:
                    raw = next(iter(states.values())).raw
                    if raw != last_raw:
                        last_raw = raw
                        print(f"  state update -> {raw!r}")
                await asyncio.sleep(0.5)

            if last_raw is not None:
                bits = ", ".join(f"PIN{p}={s.state}" for p, s in sorted(gateway.actuator_states.items()))
                print(f"OK: full 8-pin state observed — {bits}")
            else:
                print("No actuator state reports observed in the window (not necessarily a failure)")
    finally:
        await gateway.stop()

    print("OK: gateway stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
