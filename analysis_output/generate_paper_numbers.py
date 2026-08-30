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

# The six campaigns behind the five reported conditions. Must stay in step with
# EXCLUDED_CAMPAIGNS in generate_results.py, which builds combined_dataset.csv:
# 2026-05-20 (87.5%) was silently mis-throttled and is superseded by 2026-08-18,
# and the 62.5%/75% replications are reported separately, not as conditions.
REPORTED_CAMPAIGNS = [
    "2026-05-01_48h_R1_no_throtting",   # R1: llama, deepseek
    "2026-05-05_48h_R1_no_throtting",   # R1: qwen, phi3
    "2026-08-18_48h_87_5_throttling",
    "2026-06-14_48h_75_throttling",
    "2026-07-02_48h_62_5_throttling",
    "2026-07-19_48h_50_throttling",
]
R2_CAMPAIGN = "2026-05-09_48h_R2_no_throtting"

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
    """Dataset volume for the five REPORTED conditions, counted from raw files.

    Counts only the campaigns that actually feed combined_dataset.csv. Globbing
    every logs/*_48h_*/ folder instead would count nine campaigns and
    double-count three conditions, because the superseded 87.5% mis-throttle and
    the 62.5%/75% replications also live there -- an error that put the reported
    event total 63% above the sum of Table II's own cells.

    combined_dataset.csv is not used here: it drops rows whose power sample is
    missing (14 for DeepSeek@87.5%, 1105 for Phi-3@50%), understating the count.
    """
    def count(pattern, campaigns):
        total = 0
        for c in campaigns:
            for f in glob.glob(os.path.join(REPO, "logs", c, "deep_aging", pattern)):
                total += sum(1 for _ in open(f)) - 1
        return total

    events = count("*_merged_analysis.csv", REPORTED_CAMPAIGNS)
    # Power samples include the R2 replicate, which the surrounding prose
    # introduces alongside the five conditions.
    power = count("*_physical.csv", REPORTED_CAMPAIGNS + [R2_CAMPAIGN])
    return {
        "totalEvents": f"{events:,}".replace(",", "{,}"),
        "totalPowerSamples": f"{power / 1e6:.1f}",
    }


def thermal_macros(d):
    """Per-condition temperature range, as per-model means.

    Earlier drafts described a two-shelf structure, with 87.5% grouped alongside
    the unthrottled runs. That grouping was an artifact of the mis-throttled
    2026-05-20 campaign: once replaced by its verified re-execution, temperature
    falls monotonically with the cap and the shelves resolve into a gradient.
    """
    out = {}
    for cond, tag in COND_NAME.items():
        s = d[d.condition == cond].groupby("model_key").cpu_temp.mean()
        if s.empty:
            continue
        out[f"temp{tag}Lo"] = r(s.min())
        out[f"temp{tag}Hi"] = r(s.max())
    # Total span from the unthrottled reference down to the tightest cap.
    unthrottled = d[d.condition == "R1"].groupby("model_key").cpu_temp.mean().mean()
    tightest = d[d.condition == "50"].groupby("model_key").cpu_temp.mean().mean()
    out["tempTotalDrop"] = r(unthrottled - tightest)
    return out


# Conditions re-executed as independent replications. Each entry is
#   (macro tag, original campaign, replication campaign, nominal cap in MHz).
# The replication is deliberately NOT merged into combined_dataset.csv: Table III
# and every figure keep the original campaign as the reported condition. Both
# campaigns are read from their raw per-event merged_analysis files, unsmoothed,
# so the comparison is like-for-like -- combined_dataset.csv carries a 60-sample
# moving average and is not directly comparable to these numbers.
#
# Each replication is also the first run of its condition to carry 1 Hz frequency
# telemetry, so it supplies that condition's empirical cap verification.
# Add the 87.5% pair here once its replication campaign lands; nothing else
# needs to change.
REPLICATIONS = [
    ("SixtyTwoFive", "2026-07-02_48h_62_5_throttling",
     "2026-07-27_48h_62_5_throttling", 2188.0),
    ("SeventyFive", "2026-06-14_48h_75_throttling",
     "2026-08-08_48h_75_throttling", 2625.0),
]

# The 87.5% condition is deliberately NOT listed above. Its original campaign
# (2026-05-20) was silently mis-throttled, so comparing it against the verified
# 2026-08-18 re-execution measures a protocol failure, not run-to-run
# reproducibility -- the two are not replicates of the same condition. The
# verified campaign simply replaces the original in combined_dataset.csv
# (see EXCLUDED_CAMPAIGNS in generate_results.py); the discrepancy between them
# is reported in the Threats to Validity section instead.
MISTHROTTLED = {
    "EightySevenFive": ("2026-05-20_48h_87_5_throttling",
                        "2026-08-18_48h_87_5_throttling", 3063.0),
}


def replication_macros():
    """Per-condition replication agreement, drift, and cap verification."""
    def load(folder, key):
        p = os.path.join(REPO, "logs", folder, "deep_aging",
                         f"{key}_48.00h_merged_analysis.csv")
        return pd.read_csv(p, low_memory=False)

    def drift(d, fn):
        s = d[["timestamp", TPS]].dropna()
        t = ((s.timestamp - s.timestamp.min()) / 3600.0).to_numpy()
        return fn(t, s[TPS].to_numpy())

    out = {}
    all_deltas, stable_deltas = [], []

    for tag, old_folder, new_folder, cap in REPLICATIONS:
        deltas, cap_means = {}, []
        for name, key in MODELS.items():
            o, n = load(old_folder, key), load(new_folder, key)
            d = 100 * (n.tokens_per_joule.mean() / o.tokens_per_joule.mean() - 1)
            deltas[name] = d
            all_deltas.append(abs(d))
            if name != "Phi":
                stable_deltas.append(abs(d))
            cap_means.append(n.freq_khz_max_mean.dropna().mean() / 1000.0)
            if name == "Phi":
                out[f"repPhi{tag}OldOls"] = f"{drift(o, ols_drift_pct):.1f}"
                out[f"repPhi{tag}NewOls"] = f"{drift(n, ols_drift_pct):.1f}"
                out[f"repPhi{tag}OldObs"] = f"{drift(o, endpoint_pct):.1f}"
                out[f"repPhi{tag}NewObs"] = f"{drift(n, endpoint_pct):.1f}"

        out[f"rep{tag}Max"] = f"{max(abs(v) for v in deltas.values()):.1f}"
        out[f"cap{tag}Lo"] = r(min(cap_means))
        out[f"cap{tag}Hi"] = r(max(cap_means))
        out[f"cap{tag}Pct"] = r(100 * (sum(cap_means) / len(cap_means)) / cap)
        # Individual model deltas, kept for the 62.5% pair the prose enumerates.
        for name, d in deltas.items():
            out[f"rep{tag}{name}"] = f"{d:.1f}"

    out["repAllMax"] = f"{max(all_deltas):.1f}"
    out["repStableMax"] = f"{max(stable_deltas):.1f}"
    out["repConditions"] = str(len(REPLICATIONS))

    # The mis-throttled 87.5% campaign, quantified for Threats to Validity:
    # how far the superseded run departs from its verified replacement.
    for tag, (old_folder, new_folder, cap) in MISTHROTTLED.items():
        pw, tj, tmp, caps = [], [], [], []
        for key in MODELS.values():
            o, n = load(old_folder, key), load(new_folder, key)
            pw.append(100 * (o.watts_mean.mean() / n.watts_mean.mean() - 1))
            tj.append(100 * (n.tokens_per_joule.mean() / o.tokens_per_joule.mean() - 1))
            tmp.append(o.cpu_temp.mean() - n.cpu_temp.mean())
            caps.append(n.freq_khz_max_mean.dropna().mean() / 1000.0)
        out[f"bad{tag}PowerLo"] = r(min(pw))
        out[f"bad{tag}PowerHi"] = r(max(pw))
        out[f"bad{tag}TempLo"] = r(min(tmp))
        out[f"bad{tag}TempHi"] = r(max(tmp))
        out[f"bad{tag}TjLo"] = r(min(tj))
        out[f"bad{tag}TjHi"] = r(max(tj))
        out[f"cap{tag}Lo"] = r(min(caps))
        out[f"cap{tag}Hi"] = r(max(caps))
        out[f"cap{tag}Pct"] = r(100 * (sum(caps) / len(caps)) / cap)
    return out


# Campaigns containing Phi-3 that are valid measurements, i.e. every campaign
# except the two that ran without an effective cap. The replications are
# included: for characterising a phenomenon, an independent repeat of a
# condition is evidence, even though it is not a reported condition.
PHI_VALID = [
    "2026-05-05_48h_R1_no_throtting",
    "2026-05-09_48h_R2_no_throtting",
    "2026-06-14_48h_75_throttling",
    "2026-07-02_48h_62_5_throttling",
    "2026-07-19_48h_50_throttling",
    "2026-07-27_48h_62_5_throttling",
    "2026-08-08_48h_75_throttling",
    "2026-08-18_48h_87_5_throttling",
]


def phi_characterisation_macros():
    """Characterise the Phi-3 decline without asserting a mechanism.

    Three observations, each computed per campaign and reported as a range:
      - prefill throughput is flat while decode falls, so the decline is
        confined to the decode path rather than being system-wide;
      - the decline is a discrete step between plateaus, not a gradual decay;
      - the step magnitude is consistent even though its timing is not.

    Read from raw per-event files, unsmoothed. A campaign counts as degrading if
    its end-of-run median sits more than 2% below its start-of-run median --
    comfortably below the 4-7% steps and above run-to-run reproducibility.
    """
    pre, dec, steps, degraded = [], [], [], 0
    for folder in PHI_VALID:
        f = os.path.join(REPO, "logs", folder, "deep_aging",
                         "phi3_mini_48.00h_merged_analysis.csv")
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f, low_memory=False).dropna(
            subset=["timestamp", "decode_tps", "prefill_tps"]).sort_values("timestamp")
        t = ((d.timestamp - d.timestamp.min()) / 3600.0).to_numpy()
        pre.append(endpoint_pct(t, d.prefill_tps.to_numpy()))
        dec.append(endpoint_pct(t, d.decode_tps.to_numpy()))

        # Largest one-hour drop in a rolling median: isolates the step from the
        # plateaus on either side of it.
        sm = d.decode_tps.rolling(201, center=True, min_periods=50).median().to_numpy()
        hb = np.array([np.nanmedian(sm[(t >= h) & (t < h + 1)]) for h in range(48)])
        diffs = np.diff(hb)
        k = int(np.nanargmin(diffs))
        # The step range must be taken over degrading campaigns only. Including a
        # campaign that never stepped drags the lower bound down to its largest
        # ordinary fluctuation, which would contradict the very consistency the
        # range is quoted to demonstrate.
        if 100.0 * (np.nanmedian(hb[-3:]) / np.nanmedian(hb[:3]) - 1) < -2.0:
            degraded += 1
            steps.append(100.0 * diffs[k] / hb[k])

    return {
        "phiPrefillLo": f"{min(pre):.1f}", "phiPrefillHi": f"{max(pre):+.1f}",
        "phiDecodeLo": f"{min(dec):.1f}", "phiDecodeHi": f"{max(dec):.1f}",
        "phiStepLo": f"{abs(max(steps)):.1f}", "phiStepHi": f"{abs(min(steps)):.1f}",
        "phiCampaigns": str(len(dec)), "phiDegraded": str(degraded),
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
    macros.update(replication_macros())
    macros.update(phi_characterisation_macros())

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
