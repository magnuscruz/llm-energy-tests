#!/usr/bin/env python3
"""Ambient temperature and humidity from a ThermoPro BLE sensor.

A sibling of ambient_logger.py, which reads an SHT31-D over I2C, and written
because that sensor has been the weak link: a loose VDD/GND contact produced
one run of 30,449 consecutive failed reads and left the ambient record at
73.5% coverage. The failure mode was specific to a wired bus that can wedge
while still acknowledging its address.

This one cannot wedge in that way, because it never opens anything. The sensor
broadcasts its reading every few seconds and this listens. There is no
pairing, no GATT connection, no session to lose and nothing on the sensor that
knows it is being read. If the sensor is out of range the log shows a gap; when
it returns the readings resume, with no reset to perform.

WHERE THIS RUNS. On the Raspberry Pi, not on the node under test. The node has
Bluetooth, and using it would be simpler, but ambient measurement exists to
characterise the room from outside the machine being measured, and a collector
on the node is inside the envelope. The Pi is already there for this job.

OUTPUT. Byte-identical in shape to the I2C logger:

    timestamp,ambient_c,humidity_pct

one row per interval, UNIX epoch seconds, appended and never rewritten, so a
restart costs the samples taken while it was down and shows them as a gap.
build_data_analysis.py globs `*ambient*.csv` and merges on timestamp, so no
change is needed downstream, and the two loggers can run side by side into
different files while the new one is being trusted.

CADENCE. The sensor broadcasts on its own schedule, roughly every few seconds.
Rather than sample on that schedule, the logger keeps the most recent
advertisement and writes it on a fixed interval, so the output is uniformly
spaced like the I2C log and fuses the same way. An interval with no
advertisement at all writes nothing rather than repeating a stale value.

Usage:
    python3 src/ambient_logger_ble.py ~/ambient_ble.csv --interval 1
    python3 src/ambient_logger_ble.py /tmp/t.csv --simulate   # no hardware
"""
import argparse
import asyncio
import os
import struct
import sys
import time

MAX_AGE_S = 90.0          # a reading older than this is stale, not a reading
NAME_PREFIXES = ("TP35", "TP39")


def decode(company_id: int, payload: bytes):
    """Decode a TP3-family advertisement, or return None.

    The layout is thermopro-ble's for the TP357S/TP397/TP393 family, which the
    TP351S is assumed to share until scripts/ble_probe_thermopro.py confirms it
    against the vendor app. The sensor has no display of its own.

    THE INDEXING LOOKS WRONG AND IS NOT. Temperature is read from data[1:3],
    where data is the company id followed by the payload -- so it straddles the
    company id's high byte and the payload's first byte. That is not an
    off-by-one. These sensors do not use an assigned company identifier: they
    broadcast a flat frame, and BlueZ (and WinRT) split its first two bytes off
    as a company id because that is what the manufacturer-data field means.
    Reassembling them is what puts the frame back together. The on-air layout
    is one spare byte, then int16 little-endian temperature in tenths, then
    humidity, then battery flags. Verified against thermopro-ble's own source,
    not inferred: an earlier attempt to test this function failed because the
    TEST built the frame the obvious way, and the obvious way is wrong.
    """
    data = struct.pack("<H", company_id) + payload
    if len(data) < 5:
        return None
    if data[1:4] == b"\xff\xff\xff":      # the sensor's own "no reading"
        return None
    temp = struct.unpack("<h", data[1:3])[0] / 10.0
    humi = data[3]
    if not (-40.0 <= temp <= 85.0) or not (0 <= humi <= 100):
        return None                       # outside the part's range: not ours
    return temp, humi


class Simulated:
    """Enough to exercise the file handling without a sensor present."""

    def __init__(self):
        self.t0 = time.monotonic()

    def latest(self):
        import math
        t = time.monotonic() - self.t0
        return (22.0 + 2.5 * math.sin(t / 600.0),
                55.0 + 8.0 * math.sin(t / 900.0), time.monotonic())


class Listener:
    """Holds the most recent advertisement, with the time it arrived."""

    def __init__(self, address=None):
        self.address = address.lower() if address else None
        self._value = None

    def on_adv(self, device, adv):
        name = adv.local_name or device.name or ""
        if self.address:
            if device.address.lower() != self.address:
                return
        elif not name.startswith(NAME_PREFIXES):
            return
        for cid, payload in (adv.manufacturer_data or {}).items():
            got = decode(cid, payload)
            if got:
                self._value = (got[0], got[1], time.monotonic())
                return

    def latest(self):
        return self._value


def _last_timestamp(path):
    """Resume monotonically across restarts, not only within one run."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 4096))
            tail = fh.read().decode(errors="ignore").strip().splitlines()
        for line in reversed(tail):
            field = line.split(",")[0]
            if field.isdigit():
                return int(field)
    except OSError:
        pass
    return None


async def run(out_path, interval, listener, scanner, scan_window=None):
    """Append one row per interval.

    If scan_window is shorter than interval, the radio is only on for that
    window each cycle and idle for the rest. That matters when the logger runs
    on the node under test: the AX211 is a combined Wi-Fi and Bluetooth part
    sharing one front end, and the node also polls the power meter over the
    network every second. A continuous scan contends with that for no benefit,
    because the sensor broadcasts every few seconds and one row a minute is
    ample for a room.
    """
    header_needed = not os.path.exists(out_path) or os.path.getsize(out_path) == 0
    with open(out_path, "a", buffering=1) as fh:
        if header_needed:
            fh.write("timestamp,ambient_c,humidity_pct\n")
        duty = scanner is not None and scan_window and scan_window < interval
        if scanner is not None and not duty:
            await scanner.start()
        next_at = time.monotonic()
        written = skipped = nonmono = 0
        last_ts = _last_timestamp(out_path)
        try:
            while True:
                next_at += interval
                if duty:
                    # Listen at the END of the cycle, so the row carries a
                    # reading taken moments before it, not one a minute stale.
                    await asyncio.sleep(max(0.0, next_at - scan_window
                                            - time.monotonic()))
                    await scanner.start()
                    await asyncio.sleep(max(0.0, next_at - time.monotonic()))
                    await scanner.stop()
                else:
                    # Absolute schedule, so a slow write never accumulates drift.
                    await asyncio.sleep(max(0.0, next_at - time.monotonic()))
                got = listener.latest()
                if got is None or (time.monotonic() - got[2]) > MAX_AGE_S:
                    skipped += 1
                    if skipped in (10, 60, 600) or skipped % 3600 == 0:
                        age = "never" if got is None else f"{time.monotonic()-got[2]:.0f}s old"
                        print(f"[warn] {skipped} intervals without a fresh reading "
                              f"({age}); writing nothing rather than repeating",
                              file=sys.stderr, flush=True)
                    continue
                if skipped:
                    print(f"[info] reading returned after {skipped} intervals",
                          file=sys.stderr, flush=True)
                    skipped = 0
                # The wall clock can step. build_data_analysis.py SORTS the
                # ambient log before merging rather than rejecting it, so a row
                # stamped out of order is not an error there -- it is silently
                # reattributed to the wrong moment. Guaranteeing the sequence
                # is monotonic costs nothing here and nothing can fix it later.
                ts = int(time.time())
                if last_ts is not None and ts <= last_ts:
                    nonmono += 1
                    if nonmono in (1, 10, 100) or nonmono % 1000 == 0:
                        print(f"[warn] clock not advancing: {ts} <= {last_ts}; "
                              f"{nonmono} rows dropped rather than written out "
                              f"of order", file=sys.stderr, flush=True)
                    continue
                last_ts = ts
                fh.write(f"{ts},{got[0]:.2f},{got[1]:.1f}\n")
                written += 1
        finally:
            if scanner is not None:
                try:
                    await scanner.stop()
                except Exception:
                    pass
            print(f"[info] stopped after {written} rows, {skipped} intervals "
              f"without a fresh reading, {nonmono} dropped for a stalled or "
              f"backward clock", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output", help="CSV path to append to")
    ap.add_argument("--interval", type=float, default=60.0,
                    help="seconds between rows (default 60; a room does not "
                         "move faster than that, and merge_asof carries the "
                         "last reading forward to every inference)")
    ap.add_argument("--scan-window", type=float, default=8.0,
                    help="seconds of radio time per interval (default 8). Set "
                         "it >= --interval to scan continuously.")
    ap.add_argument("--address", default=None,
                    help="bind to one sensor's MAC, rather than any TP3x in range")
    ap.add_argument("--simulate", action="store_true",
                    help="no Bluetooth; synthesise a plausible room")
    a = ap.parse_args()

    if a.simulate:
        asyncio.run(run(a.output, a.interval, Simulated(), None, a.scan_window))
        return
    try:
        from bleak import BleakScanner
    except ImportError:
        sys.exit("bleak not installed: pip install bleak")
    listener = Listener(a.address)
    scanner = BleakScanner(detection_callback=listener.on_adv)
    asyncio.run(run(a.output, a.interval, listener, scanner, a.scan_window))


if __name__ == "__main__":
    main()
