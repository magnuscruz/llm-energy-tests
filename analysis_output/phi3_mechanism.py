"""Narrow down the mechanism behind Phi-3 Mini's sustained throughput decline.

The decline is reproducible across seven campaigns, and Section IV-E rules out
thermal causation (power and temperature fall alongside throughput). What it
does not establish is *where* in the pipeline the time goes. The fused telemetry
already separates prefill from decode, so the first discrimination is free:

  - prefill and decode both decline  -> system-wide (allocator, scheduler, engine)
  - decode declines, prefill flat    -> the decode path specifically, which is
                                        where the KV cache lives
  - prefill declines, decode flat    -> prompt processing, i.e. cache/context
                                        handling before generation starts

Prefill is compute-bound and touches the KV cache only to fill it; decode is
bandwidth-bound and re-reads it every token. Splitting them separates a growing
cache from a degrading allocator.
"""
import glob
import os

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS = ["phi3_mini", "qwen2.5_0.5b", "llama3.1_8b", "deepseek-v2_lite"]
CAMPAIGNS = {
    "R1": "2026-05-05_48h_R1_no_throtting",
    "R2": "2026-05-09_48h_R2_no_throtting",
    "87.5%": "2026-08-18_48h_87_5_throttling",
    "75%": "2026-08-08_48h_75_throttling",
    "62.5%": "2026-07-27_48h_62_5_throttling",
}


def load(folder, model):
    p = os.path.join(REPO, "logs", folder, "deep_aging",
                     f"{model}_48.00h_merged_analysis.csv")
    return pd.read_csv(p, low_memory=False) if os.path.exists(p) else None


def pct_change(t, y):
    """% change between first-hour and last-hour means."""
    return 100.0 * (y[t >= t.max() - 1].mean() / y[t <= t.min() + 1].mean() - 1)


def hours(d):
    return ((d.timestamp - d.timestamp.min()) / 3600.0).to_numpy()


def main():
    print("Change from first hour to last hour, per metric (%)\n")
    print(f"{'campaign':>8} {'model':>17} {'prefill':>9} {'decode':>9} "
          f"{'prefill_s':>10} {'decode_s':>9} {'interval_s':>11} {'ram_mb':>8}")

    for label, folder in CAMPAIGNS.items():
        for m in MODELS:
            d = load(folder, m)
            if d is None:
                continue
            d = d.dropna(subset=["timestamp", "prefill_tps", "decode_tps"])
            t = hours(d)
            cols = ["prefill_tps", "decode_tps", "prefill_dur_s",
                    "decode_dur_s", "inference_duration_s", "ram_used_mb"]
            vals = [pct_change(t, d[c].to_numpy()) if c in d else float("nan")
                    for c in cols]
            print(f"{label:>8} {m:>17} " +
                  " ".join(f"{v:>9.1f}" for v in vals[:2]) +
                  " " + " ".join(f"{v:>9.1f}" for v in vals[2:]))
        print()

    # Phi-3 only: when does the decline start? A late onset points to state that
    # accumulates; a linear one points to something present from the beginning.
    print("=== Phi-3: decode throughput by 6-hour block, % of first block ===")
    for label, folder in CAMPAIGNS.items():
        d = load(folder, "phi3_mini")
        if d is None:
            continue
        d = d.dropna(subset=["timestamp", "decode_tps"])
        t = hours(d)
        blocks = []
        for lo in range(0, 48, 6):
            sel = (t >= lo) & (t < lo + 6)
            blocks.append(d.decode_tps.to_numpy()[sel].mean() if sel.any() else np.nan)
        base = blocks[0]
        print(f"  {label:>8}: " + " ".join(f"{100 * b / base:5.1f}" for b in blocks))


if __name__ == "__main__":
    main()
