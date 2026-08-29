"""Compare the two independent 62.5% campaigns.

2026-05-20 is the campaign used in the paper; it predates continuous frequency
logging and relies on a sysfs cap read-back taken at campaign start.
2026-08-18 is a later re-execution that carries 1 Hz frequency telemetry, so it
both replicates the condition and verifies empirically that the cap held.
"""
import os

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OLD = os.path.join(REPO, "logs", "2026-05-20_48h_87_5_throttling", "deep_aging")
NEW = os.path.join(REPO, "logs", "2026-08-18_48h_87_5_throttling", "deep_aging")
MODELS = ["qwen2.5_0.5b", "phi3_mini", "deepseek-v2_lite", "llama3.1_8b"]
CAP_MHZ = 3063  # 62.5% of the 3.5 GHz E-core maximum


def load(base, model):
    p = os.path.join(base, f"{model}_48.00h_merged_analysis.csv")
    return pd.read_csv(p, low_memory=False) if os.path.exists(p) else None


def drift(d):
    """Total % change in decode_tps implied by an OLS slope over the run.

    Drops rows where the inference engine returned no token count (a handful
    per campaign, <0.05%); numpy would otherwise propagate NaN into the fit.
    """
    s = d[["timestamp", "decode_tps"]].dropna()
    t = (s.timestamp - s.timestamp.min()) / 3600.0
    b, a = np.polyfit(t, s.decode_tps, 1)
    return 100.0 * (b * (t.max() - t.min())) / (a + b * t.min())


def endpoint(d):
    """% change between first-hour and last-hour mean decode throughput."""
    s = d[["timestamp", "decode_tps"]].dropna()
    t = (s.timestamp - s.timestamp.min()) / 3600.0
    first = s.decode_tps[t <= 1].mean()
    last = s.decode_tps[t >= t.max() - 1].mean()
    return 100.0 * (last / first - 1)


def main():
    print(f"{'model':>17} {'metric':>14} {'2026-05-20':>12} {'2026-08-18':>12} {'delta':>9}")
    print("-" * 70)
    for m in MODELS:
        o, n = load(OLD, m), load(NEW, m)
        if o is None or n is None:
            print(f"{m:>17}  MISSING (old={o is not None}, new={n is not None})")
            continue
        rows = [
            ("events", len(o), len(n)),
            ("decode_tps", o.decode_tps.mean(), n.decode_tps.mean()),
            ("watts_mean", o.watts_mean.mean(), n.watts_mean.mean()),
            ("tokens/joule", o.tokens_per_joule.mean(), n.tokens_per_joule.mean()),
            ("cpu_temp", o.cpu_temp.mean(), n.cpu_temp.mean()),
            ("drift OLS %", drift(o), drift(n)),
            ("drift endpt %", endpoint(o), endpoint(n)),
        ]
        for label, a, b in rows:
            rel = 100.0 * (b / a - 1) if a else float("nan")
            fmt = "12.0f" if label == "events" else "12.3f"
            print(f"{m:>17} {label:>14} {a:{fmt}} {b:{fmt}} {rel:>8.1f}%")
        print()

    print("=== cap verification, only possible on the 2026-08-18 campaign ===")
    print(f"nominal cap: {CAP_MHZ} MHz")
    for m in MODELS:
        n = load(NEW, m)
        if n is None or "freq_khz_max_mean" not in n.columns:
            continue
        f = n.freq_khz_max_mean.dropna() / 1000.0
        print(f"  {m:>17}  mean={f.mean():7.1f} MHz  p95={f.quantile(.95):7.1f}  "
              f"max={f.max():7.1f}  ({100 * f.mean() / CAP_MHZ:.1f}% of cap)")


if __name__ == "__main__":
    main()
