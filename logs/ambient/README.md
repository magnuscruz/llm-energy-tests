# Indoor ambient record

`ambient_20260924.csv` was collected from the Pi (`magnuspi`, 192.168.0.158) on
2026-09-24, the first time it was copied off the device at all. Columns:
`timestamp` (UNIX epoch), `ambient_c`, `humidity_pct`. Sampling is sub-minute,
roughly one reading every 2.3 s.

The file spans 2026-09-18 13:58 to 2026-09-24 08:13 (138.2 h) and carries eight
gaps longer than five minutes, the largest of 42.8 h.

## What it covers of campaign R3, and what it does not

R3 ran 2026-09-07 14:15 to 2026-09-20 13:52, 311.6 h across four sequential
models. Coverage below is the fraction of each window lying within five minutes
of an ambient sample.

| Window | Samples | Coverage | Largest gap |
|---|---|---|---|
| R3, whole campaign | 18,281 | 1.6 % | 42.8 h |
| DeepSeek-v2 Lite run | 18,281 | 10.6 % | 42.8 h |
| Llama 3.1 8B run | 0 | 0 % | — |
| Phi-3 Mini run | 0 | 0 % | — |
| Qwen2.5 0.5B run | 0 | 0 % | — |

Every ambient sample that falls inside R3 falls inside the DeepSeek run. The
other three models have no indoor record at all, because the logger's output was
truncated on 2026-09-18, part way through the campaign.

This supersedes an earlier figure of "24 % of the window" that reached
`threats/index.tex` and `logs/MANIFEST.md`. That number was measured before the
file was ever copied off the Pi and is not reproducible from it. The true
coverage is far lower, and the more consequential fact is not the percentage but
that three of the four runs have none.

## Collection history

| collected | lines | span | coverage | largest gap |
|---|---|---|---|---|
| `ambient_20260924.csv` | 212,835 | 138.2 h | — | 42.8 h |
| `ambient_20261002.csv` | 871,519 | 329.7 h | 73.5 % | 42.8 h |

The file on the Pi is cumulative and is not truncated between collections, so
each file supersedes the one before it. They are kept separately rather than
replaced because a collection is evidence of what the record looked like on the
day it was taken.

Coverage is the fraction of the window within five minutes of a sample. At
73.5 % over fourteen days the sensor is losing roughly a quarter of the time, in
nine episodes longer than five minutes, the three largest being 42.8 h, 29.2 h
and 8.5 h. That is a reliability problem in the instrument, not an occasional
glitch, and `src/ambient_logger.py` records what is known about its cause.
