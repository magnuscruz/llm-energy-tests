"""Emit every drift-prone prose number of the paper as a LaTeX macro.

Writes ../../IEEETransactions/numbers.tex, which main.tex \\input's, so the
manuscript cites \\gainLlama instead of a hand-typed "+74\\%". Regenerate after
any change to the campaign data; the paper then cannot drift from the dataset.

Percentages derive from UNROUNDED means. Computing them from the three-decimal
values displayed in Table III is what produced the original discrepancies
(the recessions were off by up to 0.4 percentage points).
"""
import glob
import os
import re
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAPER = os.path.abspath(os.path.join(REPO, "..", "IEEETransactions"))
DATA = os.path.join(REPO, "analysis_output", "combined_dataset.csv")
OUT = os.path.join(PAPER, "numbers.tex")

# The original 2026-07-11 50% campaign ran without an effective cap; the
# hardened re-execution is 2026-07-19. Never mix them.
INVALID_CAMPAIGN = "2026-07-11_48h_50_throttling"

HOURS = "Time (Hours)"
TPS = "decode_tps"

MODELS = {
    "Llama": "llama3.1_8b",
    "Phi": "phi3_mini",
    "Deepseek": "deepseek-v2_lite",
    "Qwen": "qwen2.5_0.5b",
}
THROTTLED = ["87_5", "75", "62_5", "50"]
COND_NAME = {"R1": "Rone", "R2": "Rtwo", "87_5": "EightySevenFive",
             "75": "SeventyFive", "62_5": "SixtyTwoFive", "50": "Fifty"}


def r(value, places=0):
    """Round half-UP, the convention a reader assumes.

    numpy rounds half-to-even, which turns a 52.5% gain into 52 rather than 53.
    That boundary case is why generated macros can disagree with hand-written
    prose, so pin the behaviour explicitly.
    """
    q = Decimal(1) if places == 0 else Decimal(f"1.{'0' * places}")
    return str(Decimal(float(value)).quantize(q, rounding=ROUND_HALF_UP))


def series(d, model_key, cond):
    """Return (elapsed_hours, decode_tps) for one model/condition, or None."""
    s = d[(d.model_key == model_key) & (d.condition == cond)].sort_values(HOURS)
    if len(s) < 50:
        return None
    return s[HOURS].to_numpy(), s[TPS].to_numpy()


def ols_drift_pct(x, y):
    """Total % change implied by an OLS slope across the observed span."""
    b, a = np.polyfit(x, y, 1)
    return 100.0 * (b * (x.max() - x.min())) / (a + b * x.min())


def endpoint_pct(x, y):
    """% change between first-hour and last-hour means.

    Hour-wide windows rather than a fixed event count: event rates vary ~16x
    across conditions, so a fixed count spans very different wall-clock spans.
    """
    return 100.0 * (y[x >= x.max() - 1].mean() / y[x <= x.min() + 1].mean() - 1)


def efficiency_macros(tj):
    """Eco-efficiency gains (R1 -> best throttled) and peak -> 50% recessions."""
    out = {}
    gains = {}
    for name, key in MODELS.items():
        gains[name] = 100 * (tj.loc[key, THROTTLED].max() / tj.loc[key, "R1"] - 1)
        out[f"gain{name}"] = r(gains[name])
        peak = tj.loc[key, THROTTLED].max()
        out[f"rec{name}"] = r(100 * (tj.loc[key, "50"] / peak - 1), 1)
    out["gainRangeLo"] = r(min(gains.values()))
    out["gainRangeHi"] = r(max(gains.values()))
    return out


def throughput_power_macros(tps, pw):
    """Throughput loss and power drop from R1 to the 62.5% cap, with endpoints."""
    out = {}
    for name, key in MODELS.items():
        out[f"loss{name}"] = r(abs(100 * (tps.loc[key, "62_5"] / tps.loc[key, "R1"] - 1)))
        out[f"pdrop{name}"] = r(abs(100 * (pw.loc[key, "62_5"] / pw.loc[key, "R1"] - 1)))
        out[f"tpsRone{name}"] = f"{tps.loc[key, 'R1']:.1f}"
        out[f"tpsSixtyTwoFive{name}"] = f"{tps.loc[key, '62_5']:.1f}"
        out[f"wattRone{name}"] = r(pw.loc[key, "R1"])
        out[f"wattSixtyTwoFive{name}"] = r(pw.loc[key, "62_5"])
    return out


def drift_macros(d):
    """Per-condition throughput drift, by OLS slope and by endpoint comparison.

    Both are reported in the paper. The OLS slope returns roughly double the
    endpoint magnitude for Phi-3, because a linear fit assumes a constant decay
    rate while Phi-3 holds steady for about half the run and falls afterwards.
    That divergence is itself the evidence that the decline is late-onset.
    """
    out = {}
    worst_other = 0.0
    endpoint_mags = []
    for name, key in MODELS.items():
        for cond, tag in COND_NAME.items():
            xy = series(d, key, cond)
            if xy is None:
                continue
            x, y = xy
            pct = ols_drift_pct(x, y)
            if name != "Phi":
                worst_other = max(worst_other, abs(pct))
                continue
            out[f"driftPhi{tag}"] = f"{pct:.1f}"
            ep = endpoint_pct(x, y)
            out[f"obsPhi{tag}"] = f"{ep:.1f}"
            endpoint_mags.append(abs(ep))
    out["driftOthersMax"] = f"{worst_other:.1f}"
    out["obsPhiMax"] = f"{max(endpoint_mags):.1f}"
    return out


def phi_decline_macros(d):
    """Phi-3 at R1: power and temperature fall alongside throughput.

    This is what excludes thermal throttling as the cause of the degradation.
    """
    out = {}
    s = d[(d.model_key == "phi3_mini") & (d.condition == "R1")].sort_values(HOURS)
    x = s[HOURS].to_numpy()
    for col, tag in [("watts_mean", "Watt"), ("cpu_temp", "Temp")]:
        out[f"phiRoneDecline{tag}"] = f"{abs(ols_drift_pct(x, s[col].to_numpy())):.1f}"
    return out


def volume_macros():
    """Dataset volume, counted from the RAW files.

    combined_dataset.csv drops rows with NaN power (14 for DeepSeek@87.5%,
    1105 for Phi-3@50%), so counting there understates the campaign.
    """
    def count(pattern, skip_r2):
        total = 0
        for f in glob.glob(os.path.join(REPO, "logs", "*_48h_*", "deep_aging", pattern)):
            if INVALID_CAMPAIGN in f or (skip_r2 and "_R2_" in f):
                continue
            total += sum(1 for _ in open(f)) - 1
        return total

    return {
        "totalEvents": f"{count('*_merged_analysis.csv', True):,}".replace(",", "{,}"),
        "totalPowerSamples": f"{count('*_physical.csv', False) / 1e6:.1f}",
    }


def thermal_macros(d):
    """Hot/cool temperature shelves, equal weight per model x condition."""
    hot = d[d.condition.isin(["R1", "R2", "87_5"])].groupby(
        ["model_key", "condition"]).cpu_temp.mean()
    cool = d[d.condition.isin(["75", "62_5"])].groupby(
        ["model_key", "condition"]).cpu_temp.mean()
    return {
        "shelfHotLo": r(hot.min()),
        "shelfHotHi": r(hot.max()),
        "shelfCoolLo": r(cool.min()),
        "shelfCoolHi": r(cool.max()),
        "shelfGap": r(hot.mean() - cool.mean()),
    }


def report_hardcoded():
    """Print numbers still typed by hand in the sources, so drift stays visible."""
    print("\n=== still hardcoded in the .tex sources ===")
    src = "".join(open(os.path.join(PAPER, f)).read() for f in
                  ["main.tex", "intro/index.tex", "results/index.tex",
                   "methodology/index.tex", "threats/index.tex"])
    for label, pat in [
        ("gain range", r"\d+--\d+\\% gain"),
        ("phi drift R1", r"\$-\d+\.\d\\%\$ over 48~h at R1"),
        ("recessions", r"by \$-\d\.\d\\%\$ for Qwen[^,]*"),
        ("shelf gap", r"roughly a \d+\\,\$\^\{\\circ\}\$C gap"),
        ("cool shelf", r"``cool'' shelf of \d+--\d+"),
    ]:
        hits = re.findall(pat, src)
        print(f"  {label:16s}: {hits if hits else 'not found'}")


def main():
    d = pd.read_csv(DATA, low_memory=False)

    def pivot(col):
        return d.pivot_table(index="model_key", columns="condition",
                             values=col, aggfunc="mean")

    macros = {}
    macros.update(efficiency_macros(pivot("tokens_per_joule")))
    macros.update(throughput_power_macros(pivot(TPS), pivot("watts_mean")))
    macros.update(drift_macros(d))
    macros.update(phi_decline_macros(d))
    macros.update(volume_macros())
    macros.update(thermal_macros(d))

    with open(OUT, "w") as fh:
        fh.write("% AUTO-GENERATED by analysis_output/generate_paper_numbers.py.\n")
        fh.write("% Do not edit by hand; regenerate after any data change.\n")
        fh.write("% All percentages derive from unrounded means.\n\n")
        for k in sorted(macros):
            fh.write(f"\\newcommand{{\\{k}}}{{{macros[k]}}}\n")

    print(f"wrote {OUT} with {len(macros)} macros\n")
    for k in sorted(macros):
        print(f"  \\{k:28s} = {macros[k]}")
    report_hardcoded()


if __name__ == "__main__":
    main()
