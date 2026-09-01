"""Out-of-band ambient temperature and humidity logger (SHT31-D over I2C).

Runs on a separate machine from the node under test -- a Raspberry Pi Zero 2 W
in our setup -- so that sampling the room costs the measured node nothing. This
mirrors the rationale for metering power at the wall rather than in software.

Output schema follows the other telemetry streams: one row per sample, anchored
to the UNIX epoch so the fusion pipeline can join it with merge_asof exactly as
it joins the 1 Hz power log.

    timestamp,ambient_c,humidity_pct

Wiring (Pi Zero 2 W, 40-pin header):
    VIN -> pin 1  (3V3)   <-- 3.3 V, NOT 5 V: the board's I2C pull-ups may sit
    GND -> pin 6  (GND)       on VIN, and the Pi's GPIO are not 5 V tolerant.
    SDA -> pin 3  (GPIO2)
    SCL -> pin 5  (GPIO3)

Enable I2C first (raspi-config, or dtparam=i2c_arm=on in /boot/config.txt),
then confirm the sensor answers:  i2cdetect -y 1   ->  0x44 (or 0x45)

Mount the sensor on a lead, well away from both this Pi and the exhaust of the
node under test. A sensor sitting on warm hardware measures the hardware.
"""
import argparse
import math
import random
import struct
import time

try:
    from smbus2 import SMBus, i2c_msg
except ImportError:                      # --simulate needs no I2C stack
    SMBus = i2c_msg = None

I2C_BUS = 1
ADDR_DEFAULT = 0x44          # 0x45 if the ADDR pad is pulled high
CMD_SINGLE_HIGH_REP = (0x24, 0x00)   # single shot, clock stretching disabled
MEAS_DELAY_S = 0.016         # datasheet: 15 ms max for high repeatability


def crc8(data: bytes) -> int:
    """Sensirion CRC-8: polynomial 0x31, init 0xFF."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def read_sample(bus: SMBus, addr: int):
    """Return (temperature_c, humidity_pct), or None if a CRC check fails."""
    bus.write_i2c_block_data(addr, CMD_SINGLE_HIGH_REP[0], [CMD_SINGLE_HIGH_REP[1]])
    time.sleep(MEAS_DELAY_S)
    read = i2c_msg.read(addr, 6)
    bus.i2c_rdwr(read)
    raw = bytes(read)

    t_raw, t_crc, h_raw, h_crc = struct.unpack(">HBHB", raw)
    if crc8(raw[0:2]) != t_crc or crc8(raw[3:5]) != h_crc:
        return None

    # Datasheet conversions (SHT3x, 16-bit).
    return (-45 + 175 * t_raw / 65535.0, 100 * h_raw / 65535.0)


class FakeSensor:
    """Plausible readings, so the logger and the fusion step can be exercised
    end to end before the hardware exists.

    Everything downstream of the I2C read -- schema, epoch stamping, cadence,
    the merge_asof join -- is worth validating on its own. Waiting for the
    sensor to test the pipeline means discovering pipeline bugs during a
    48-hour campaign, which is when they are most expensive.

    A slow diurnal swing plus per-sample noise; the point is realistic shape,
    not physical fidelity.
    """

    def __init__(self, base_c=22.0, swing_c=2.5, base_rh=55.0):
        self.base_c, self.swing_c, self.base_rh = base_c, swing_c, base_rh
        self.t0 = time.time()

    def read(self):
        hours = (time.time() - self.t0) / 3600.0
        drift = self.swing_c * math.sin(2 * math.pi * hours / 24.0)
        return (self.base_c + drift + random.gauss(0, 0.05),
                self.base_rh - drift * 2 + random.gauss(0, 0.3))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", help="CSV path to append to")
    p.add_argument("--interval", type=float, default=1.0,
                   help="seconds between samples (default: 1.0)")
    p.add_argument("--address", type=lambda x: int(x, 0), default=ADDR_DEFAULT,
                   help="I2C address, 0x44 or 0x45 (default: 0x44)")
    p.add_argument("--simulate", action="store_true",
                   help="emit synthetic readings; no sensor or I2C stack needed")
    args = p.parse_args()

    if args.simulate:
        fake = FakeSensor()
        with open(args.output, "a", buffering=1) as fh:
            if fh.tell() == 0:
                fh.write("timestamp,ambient_c,humidity_pct\n")
            next_at = time.time()
            while True:
                t, h = fake.read()
                fh.write(f"{int(time.time())},{t:.2f},{h:.2f}\n")
                next_at += args.interval
                time.sleep(max(0.0, next_at - time.time()))
        return

    with SMBus(I2C_BUS) as bus, open(args.output, "a", buffering=1) as fh:
        if fh.tell() == 0:
            fh.write("timestamp,ambient_c,humidity_pct\n")
        # Drift-free cadence: schedule against a fixed origin rather than
        # sleeping a fixed amount, so the read time does not accumulate.
        next_at = time.time()
        while True:
            sample = read_sample(bus, args.address)
            if sample is not None:
                t, h = sample
                fh.write(f"{int(time.time())},{t:.2f},{h:.2f}\n")
            # A failed CRC is dropped rather than imputed; the fusion step
            # already tolerates gaps in the out-of-band streams.
            next_at += args.interval
            time.sleep(max(0.0, next_at - time.time()))


if __name__ == "__main__":
    main()
