#!/usr/bin/env python3
"""Find out what the ThermoPro sensor actually broadcasts, before trusting it.

The TP351S is not in thermopro-ble's tested list. Its gate is
`name.startswith(("TP35", "TP39", "TP96", "TP97"))`, so "TP351S" is let
through and falls into the generic TP3 branch, which the library's own
comments say was written for the TP357S, TP397 and TP393. It may well be the
same layout. It may not. One capture settles it, and that is all this does.

Run it on the Pi, with the sensor on the desk beside it, before anything is
deployed:

    python3 scripts/ble_probe_thermopro.py --seconds 90

It scans PASSIVELY. Nothing is paired, nothing is connected to, no state is
created on either side, and the sensor does not know it was watched. For each
advertisement from a TP3x device it prints the raw manufacturer payload, what
thermopro-ble makes of it, and what the documented byte layout would give
independently. If those two disagree, the layout does not hold for this model
and we decode it ourselves; if they agree and match the sensor's own display,
we are done.

Compare against the number on the sensor's screen while it runs. That is the
ground truth here, not either decoder.

Needs: pip install bleak thermopro-ble
"""
import argparse
import asyncio
import struct
import sys
from collections import defaultdict

try:
    from bleak import BleakScanner
except ImportError:
    sys.exit("bleak not installed: pip install bleak")

try:
    from thermopro_ble import ThermoProBluetoothDeviceData
except ImportError:
    ThermoProBluetoothDeviceData = None


def manual_decode(payload: bytes):
    """The layout thermopro-ble uses for the TP3 family, applied by hand.

    Offsets are into company-id + payload, which is how the library indexes:
    temperature is a signed little-endian 16-bit at [1:3] divided by ten,
    humidity an unsigned byte at [3], battery the low two bits of [4].
    Reproduced here so a disagreement between the two is visible rather than
    hidden inside a dependency.
    """
    if len(payload) < 5:
        return None
    if payload[1:4] == b"\xff\xff\xff":
        return "sentinel (ffffff) -- sensor reports no valid reading"
    temp = struct.unpack("<h", payload[1:3])[0] / 10.0
    humi = payload[3]
    batt = {0: 1, 1: 50, 2: 100}.get(payload[4] & 3)
    return f"{temp:.1f} C, {humi}% RH, battery {batt}%"


async def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--all", action="store_true",
                    help="print every device seen, not only TP3x ones")
    a = ap.parse_args()

    seen = defaultdict(int)
    lib = ThermoProBluetoothDeviceData() if ThermoProBluetoothDeviceData else None
    if lib is None:
        print("note: thermopro-ble not installed; showing the manual decode only\n")

    def on_adv(device, adv):
        name = adv.local_name or device.name or ""
        interesting = name.startswith(("TP35", "TP39", "TP96", "TP97"))
        if not interesting and not a.all:
            return
        seen[name or device.address] += 1
        if seen[name or device.address] > 6:
            return  # six of each is plenty to see whether it is stable

        print(f"[{device.address}] name={name!r} rssi={adv.rssi}")
        for cid, payload in (adv.manufacturer_data or {}).items():
            full = struct.pack("<H", cid) + payload
            print(f"    company 0x{cid:04x}  payload {payload.hex()}  "
                  f"({len(payload)} bytes)")
            print(f"    manual  : {manual_decode(full)}")
        if adv.service_data:
            for uuid, payload in adv.service_data.items():
                print(f"    service {uuid}: {payload.hex()}")
        if lib is not None and interesting:
            try:
                upd = lib.update(
                    type("A", (), {"name": name, "address": device.address,
                                   "rssi": adv.rssi,
                                   "manufacturer_data": adv.manufacturer_data,
                                   "service_data": adv.service_data,
                                   "service_uuids": adv.service_uuids,
                                   "source": "probe"})())
                vals = {k.key: v.native_value for k, v in upd.entity_values.items()}
                print(f"    library : {vals}")
            except Exception as e:
                print(f"    library : FAILED {type(e).__name__}: {e}")
        print()

    print(f"scanning passively for {a.seconds:.0f} s -- "
          f"compare what prints against the sensor's own display\n")
    scanner = BleakScanner(detection_callback=on_adv)
    await scanner.start()
    await asyncio.sleep(a.seconds)
    await scanner.stop()

    if not seen:
        print("nothing seen. Check the sensor is awake (press its button), that "
              "it is within a few metres, and that this machine's Bluetooth is up "
              "(bluetoothctl show).")
    else:
        print("advertisements per device:")
        for k, n in sorted(seen.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<24} {n}")


if __name__ == "__main__":
    asyncio.run(main())
