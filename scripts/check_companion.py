#!/usr/bin/env python3
"""Check whether a MeshCore companion radio is reachable over BLE or USB/serial.

Usage:
    python scripts/check_companion.py [-T timeout] [--ble-only|--serial-only]

Exits 0 if at least one MeshCore companion device was found, 1 otherwise.
"""
import argparse
import asyncio
import sys

import serial.tools.list_ports

try:
    from bleak import BleakScanner
    from bleak.exc import BleakError
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False


async def check_ble(timeout: float) -> list[str]:
    if not BLEAK_AVAILABLE:
        print("BLE: bleak not installed, skipping")
        return []
    found = []
    try:
        devices = await BleakScanner.discover(timeout=timeout)
    except BleakError as e:
        print(f"BLE: scan failed ({e})")
        return []
    for d in devices:
        if d.name and d.name.startswith("MeshCore-"):
            found.append(f"{d.address}  {d.name}")
    if found:
        print("BLE: companion(s) found:")
        for line in found:
            print(f"  {line}")
    else:
        print("BLE: no companion found")
    return found


def check_serial() -> list[str]:
    found = []
    for port, desc, hwid in sorted(serial.tools.list_ports.comports()):
        found.append(f"{port}  {desc} [{hwid}]")
    if found:
        print("Serial: port(s) found:")
        for line in found:
            print(f"  {line}")
    else:
        print("Serial: no port found")
    return found


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-T", "--timeout", type=float, default=2.0,
                         help="BLE scan timeout in seconds (default: 2)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ble-only", action="store_true")
    group.add_argument("--serial-only", action="store_true")
    args = parser.parse_args()

    ble_found: list[str] = []
    serial_found: list[str] = []

    if not args.serial_only:
        ble_found = await check_ble(args.timeout)
    if not args.ble_only:
        serial_found = check_serial()

    if ble_found or serial_found:
        print("\nOK: companion device reachable")
        return 0

    print("\nFAIL: no companion device found on BLE or serial")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
