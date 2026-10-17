# Verifying the TP351S decode — 2026-10-20

Captured with `scripts/ble_probe_thermopro.py` from Windows, sensor on the
desk, before anything was deployed. Raw capture of the third reading in
`ble_probe_20261020_raw.txt` (PowerShell's `Tee-Object` writes UTF-16; it was
converted here).

The sensor advertises as `TP351S (C505)` from `FF:FF:81:1A:C5:05`, five-byte
payload, which reassembles with the company id into a seven-byte frame.

| when | frame | decoded |
|---|---|---|
| at rest | `c2 0b 01 36 22 33 01` | 26.7 °C, 54 % |
| held under a leg | `c2 21 01 3b 22 33 01` | 28.9 °C, 59 % |
| cooling again | `c2 0f 01 37 22 33 01` | 27.1 °C, 55 % |

## What this establishes

**The TP357S layout holds for the TP351S.** `thermopro-ble` lets `TP351S`
through its `TP35` gate and into a branch its own comments say was written for
other models. It decodes correctly.

**The scale factor is /10, settled by magnitude rather than by assumption.**
Body contact moved the reading 2.2 °C. At /1 the same bytes would read a
22 °C jump, at /100 a 0.02 °C one, and a leg does neither. This is why the
differential test was worth more than comparing against the vendor app: a
plausible single number proves nothing, a number that moves correctly proves
the arithmetic.

**Only the bytes the layout calls variable varied.** `data[0]`, `data[2]` and
`data[4..6]` are identical across all three captures. Temperature's low byte
and humidity are the only things that moved.

**The "company id" is not one.** It changed across the three captures —
`0x0bc2`, `0x21c2`, `0x0fc2` — which an assigned manufacturer identifier
cannot do. Its high byte is the temperature's low byte. That is direct
evidence for why `decode()` indexes across the company id, which otherwise
reads like an off-by-one and would invite being "fixed".

## Not established

Absolute accuracy. Nothing here was compared against a calibrated instrument,
so the readings are internally consistent and of unknown trueness. For ambient
room temperature alongside a 48-hour inference campaign that is sufficient:
what the record has to support is correlation against node temperature and
power, not a claim about the room's absolute temperature.
