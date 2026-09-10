#!/usr/bin/env python3
"""Exercise the backend's MeshGateway against a real companion, without
booting FastAPI/SQLAlchemy/APScheduler.

Confirms: the gateway connects, ensure_channel() finds/keeps the configured
channel, an optional message goes out on it (fire-and-forget), and the
gateway's permanent background listener picks up the actuator's state
echoes — the same paths the OTP flow and the scheduler use in production.

The actuator answers PINx_ON/OFF asynchronously and decoupled from any
specific send (confirmed against real hardware) — so this script does NOT
try to match "this echo answers that send". It just starts the gateway
(which starts listening immediately), optionally fires a command, and
prints gateway.actuator_states over a window so you can see what arrives.

Usage:
    python scripts/test_mesh_gateway.py -s COM12 [--chan-name '#i2c-am2301']
        [--chan-idx 1] [--actuator-name Rtp-02-switch] [--send "PIN0_ON"]
        [--listen 15]

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
    print(f"Background listener active, trusting echoes from {args.actuator_name!r}")

    try:
        if args.send:
            print(f"Sending on channel {args.chan_idx}: {args.send!r} (fire-and-forget, not awaiting any reply)")
            await gateway.send_channel(args.send)
            print("OK: message sent")

        if args.listen > 0:
            print(f"Watching actuator_states for {args.listen}s (echoes arrive independently)...")
            seen: dict[int, str] = {}
            loop = asyncio.get_event_loop()
            deadline = loop.time() + args.listen
            while loop.time() < deadline:
                for pin, s in gateway.actuator_states.items():
                    if seen.get(pin) != s.raw:
                        seen[pin] = s.raw
                        print(f"  state update -> {s.raw!r}")
                await asyncio.sleep(0.5)

            if seen:
                print(f"OK: observed state for PIN(s) {sorted(seen)}")
            else:
                print("No actuator echoes observed in the window (not necessarily a failure)")
    finally:
        await gateway.stop()

    print("OK: gateway stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
