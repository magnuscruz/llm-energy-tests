"""Compare drift estimators for decode throughput over the 48h window.

The paper corroborates its OLS slope with a "first-200 vs last-200 events"
comparison. That is not sound across conditions: event rates differ by an order
of magnitude between models and caps, so a fixed count of 200 events spans very
different amounts of wall-clock time. The 'hrs/200ev' column quantifies this.

Two replacements are evaluated:
  Theil-Sen      -- robust to outliers, unlike OLS
  1st/last hour  -- time-anchored, therefore comparable across conditions
"""
import os

import numpy as np
import pandas as pd

try:
    from scipy.stats import theilslopes
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(REPO, "analysis_output", "combined_dataset.csv.gz")
CONDS = ["R1", "R2", "87_5", "75", "62_5", "50"]
MODELS = ["phi3_mini", "qwen2.5_0.5b", "llama3.1_8b", "deepseek-v2_lite"]


def pct(slope, intercept, x):
    return 100.0 * (slope * (x.max() - x.min())) / (intercept + slope * x.min())


# theilslopes evaluates every pairwise slope, i.e. O(n^2). At n=36,211 (Qwen R1)
# that is ~656M pairs and the call effectively never returns. Subsampling to a
# few thousand evenly spaced points leaves the slope estimate intact while making
# the call instant -- we are estimating one number, not resolving fine structure.
TS_MAX_POINTS = 2000


def methods(x, y):
    """Return the four drift estimates, in %, for one model/condition series."""
    b, a = np.polyfit(x, y, 1)
    out = {"OLS": pct(b, a, x)}
    if HAVE_SCIPY:
        if len(x) > TS_MAX_POINTS:
            idx = np.linspace(0, len(x) - 1, TS_MAX_POINTS).astype(int)
            xs, ys = x[idx], y[idx]
        else:
            xs, ys = x, y
        ts, ic, _, _ = theilslopes(ys, xs)
        # report over the FULL span, not the subsample's
        out["TheilSen"] = pct(ts, ic, x)
    else:
        out["TheilSen"] = float("nan")
    out["hour"] = 100.0 * (y[x >= x.max() - 1].mean() / y[x <= x.min() + 1].mean() - 1)
    out["ev200"] = 100.0 * (y[-200:].mean() / y[:200].mean() - 1)
    return out


def main():
    d = pd.read_csv(DATA, low_memory=False)
    print(f"scipy available: {HAVE_SCIPY}", flush=True)
    print(f"Theil-Sen subsampled to at most {TS_MAX_POINTS} points per series.",
          flush=True)
    print("\nDrift in decode_tps over the observed window (%)\n", flush=True)
    print(f"{'model':>17} {'cond':>5} {'OLS':>8} {'TheilSen':>9} "
          f"{'1st/lastHr':>11} {'1st/last200':>12} {'hrs/200ev':>10} {'n':>7}")

    for m in MODELS:
        for c in CONDS:
            s = d[(d.model_key == m) & (d.condition == c)].sort_values("Time (Hours)")
            if len(s) < 50:
                continue
            x = s["Time (Hours)"].to_numpy()
            y = s["decode_tps"].to_numpy()
            v = methods(x, y)
            span200 = (x[199] - x[0]) if len(x) > 200 else float("nan")
            print(f"{m:>17} {c:>5} {v['OLS']:>7.1f}% {v['TheilSen']:>8.1f}% "
                  f"{v['hour']:>10.1f}% {v['ev200']:>11.1f}% {span200:>9.2f} {len(s):>7}",
                  flush=True)
        print(flush=True)

    print("=== sign agreement across all four methods ===")
    for m in MODELS:
        for c in CONDS:
            s = d[(d.model_key == m) & (d.condition == c)].sort_values("Time (Hours)")
            if len(s) < 50:
                continue
            v = methods(s["Time (Hours)"].to_numpy(), s["decode_tps"].to_numpy())
            vals = [x for x in v.values() if not np.isnan(x)]
            tag = "all NEG" if all(x < 0 for x in vals) else (
                "all POS" if all(x > 0 for x in vals) else "MIXED")
            print(f"  {m:>17} {c:>5}  {tag:8s}  " +
                  "  ".join(f"{k}={x:+.1f}%" for k, x in v.items()))
        print()


if __name__ == "__main__":
    main()
