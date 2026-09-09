import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
OUT_DIR = os.path.dirname(__file__)

# logs/2026-07-11_48h_50_throttling is the original, pre-hardened-protocol 50%
# run: effective frequency ~2.4GHz vs the 1.75GHz cap ladder (see threats/index.tex
# in IEEETransactions). Its replacement, logs/2026-07-19_48h_50_throttling, is the
# valid hardened-protocol re-execution and must NOT be excluded.
#
# Both folders strip down to the identical test_baseline "48h_50_throttling" (the
# date prefix is removed), so excluding by that stripped string would silently
# drop BOTH campaigns or, if the exclusion set were emptied naively, merge the
# invalid and valid runs together under one condition label. Exclude by the full,
# date-qualified campaign folder name instead.
#
# 2026-05-20_48h_87_5_throttling is a SECOND silently mis-throttled campaign,
# found the same way as the 50% one. Its prefill throughput sits at ~0.95 of the
# unthrottled reference, off the regular ladder traced by the three verified
# campaigns (87.5% -> 0.87, 75% -> 0.80, 62.5% -> 0.70), and it drew ~28% more
# power and ran ~8 degC hotter than the verified 87.5% re-execution. It predates
# continuous frequency logging, so nothing in its own telemetry contradicts the
# nominal cap. 2026-08-18_48h_87_5_throttling replaces it as the 87.5% condition.
#
# The 62.5% and 75% replications are excluded for a different reason: they are
# valid, but they duplicate a condition already represented by its original
# campaign. Including them would merge two runs under one condition label.
# They are analyzed separately by generate_paper_numbers.py.
EXCLUDED_CAMPAIGNS = {
    "2026-07-11_48h_50_throttling",
    "2026-05-20_48h_87_5_throttling",
    "2026-07-27_48h_62_5_throttling",
    "2026-08-08_48h_75_throttling",
}

MODEL_STYLE = {
    "llama3.1_8b":      {"label": "Llama 3.1 8B (Dense)",       "color": "#2a78d6"},
    "deepseek-v2_lite": {"label": "DeepSeek-v2 Lite (MoE)",     "color": "#eb6834"},
    "qwen2.5_0.5b":     {"label": "Qwen2.5 0.5B (Dense)",       "color": "#1baf7a"},
    "phi3_mini":        {"label": "Phi-3 Mini (Dense)",         "color": "#eda100"},
}

CONDITION_STYLE = {
    "R1":     {"label": "R1 (Unthrottled)",       "linestyle": "solid",             "lw": 3.2, "z": 5},
    "R2":     {"label": "R2 (Unthrottled, rep.)", "linestyle": (0, (6, 2)),          "lw": 2.6, "z": 4},
    "87_5":   {"label": "Throttled 87.5%",        "linestyle": (0, (1, 1)),          "lw": 2.8, "z": 3},
    "75":     {"label": "Throttled 75%",          "linestyle": (0, (3, 1, 1, 1)),    "lw": 2.8, "z": 2},
    "62_5":   {"label": "Throttled 62.5%",        "linestyle": (0, (5, 5)),          "lw": 2.8, "z": 1},
    "50":     {"label": "Throttled 50%",          "linestyle": (0, (1, 1, 3, 1)),    "lw": 2.8, "z": 0},
}
# Line-chart condition set (thermal/RAM/reproducibility figures): intentionally
# excludes 50%, matching Section IV-A/IV-B's "all five conditions" grouping
# (R1, R2, and the three original throttled points), which predates and is
# distinct from the 50%-inclusive set reported in Table III.
CONDITION_ORDER = ["R1", "R2", "87_5", "75", "62_5"]

# Superset used only for classifying rows while loading data (includes 50%,
# needed for the bar-chart / Table III condition set below).
ALL_CONDITIONS = CONDITION_ORDER + ["50"]

# Ordinal sequential ramp (one hue, light->dark) for the 5 bar-chart conditions
# (R1, 87.5, 75, 62.5, 50 -- no R2). Validated with scripts/validate_palette.js
# --ordinal (dataviz skill, palette.md); the previous 5-color set (which included
# R2 instead of 50) does not directly reuse these steps, since swapping one entry
# for a darker one changed which spacing clears the adjacent-gap floor.
CONDITION_BAR_COLOR = {
    "R1":    "#86b6ef",
    "87_5":  "#3987e5",
    "75":    "#256abf",
    "62_5":  "#184f95",
    "50":    "#0d366b",
}

# Bar-chart condition set: mirrors Table III exactly (R1 + all four throttled
# points, no R2 replicate).
BAR_CONDITIONS = ["R1", "87_5", "75", "62_5", "50"]

PAIRS = [
    ("llama3.1_8b", "deepseek-v2_lite", "pair_llama_deepseek"),
    ("qwen2.5_0.5b", "phi3_mini", "pair_qwen_phi3"),
]

METRICS = [
    ("cpu_temp", "CPU Temperature (°C)", "01_cpu_temp"),
    ("ram_used_mb", "RAM Used (MB, system-wide)", "02_ram_used_mb"),
    ("decode_tps", "Decode Throughput (tokens/s)", "03_decode_tps"),
    ("eco_efficiency_ce", "Carbon-Aware Eco-Efficiency (CE)", "04_eco_efficiency_ce"),
]

# ---- chrome (dataviz skill reference palette) ----
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "grid.color": GRID,
    "font.family": "sans-serif",
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6.5,
})
# Point sizes are real, not pre-inflated. Figures are generated at 3.5 in --
# the \columnwidth of a two-column IEEEtran page -- and reproduced at that
# width, so nothing is scaled and 8 pt prints as 8 pt.
#
# They previously used sizes around 2x, to survive a reduction from a 13 in
# canvas into a single \columnwidth column. That reduction was 3.7x, not 2x,
# which put axis labels below 6 pt on the page. If a figure's reproduction
# width in the .tex ever changes, change figsize to match it rather than
# compensating with the font sizes here.


def parse_condition(test_baseline):
    for key in ALL_CONDITIONS:
        marker = f"_{key}_"
        if marker in f"_{test_baseline}_":
            return key
    return None


def load_all():
    pattern = os.path.join(LOGS_DIR, "**", "*_merged_analysis.csv")
    rows = []
    for f in sorted(glob.glob(pattern, recursive=True)):
        filename = os.path.basename(f)
        model_key = next((m for m in MODEL_STYLE if m in filename), None)
        if model_key is None:
            continue

        test_baseline = "Unknown"
        campaign_folder = None
        current_dir = os.path.dirname(f)
        for _ in range(5):
            dir_basename = os.path.basename(current_dir)
            if dir_basename and "_" in dir_basename and any(c.isdigit() for c in dir_basename.split("_")[0]):
                campaign_folder = dir_basename
                test_baseline = "_".join(dir_basename.split("_")[1:])
                break
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
        if campaign_folder in EXCLUDED_CAMPAIGNS:
            continue
        condition = parse_condition(test_baseline)
        if condition is None:
            print(f"WARN: could not classify condition for {f} (test_baseline={test_baseline})")
            continue

        df = pd.read_csv(f)
        df = df.dropna(subset=["cpu_temp", "decode_tps", "ram_used_mb"])
        df["Time (Hours)"] = (df["timestamp"] - df["timestamp"].min()) / 3600.0
        df["model_key"] = model_key
        df["condition"] = condition
        df["test_baseline"] = test_baseline
        rows.append(df)
    full = pd.concat(rows, ignore_index=True)

    # Smoothing, matching the dashboard default (60-sample rolling mean),
    # grouped by exact run so we never smooth across different campaigns.
    numeric_cols = [c for c in ["cpu_temp", "ram_used_mb", "decode_tps", "eco_efficiency_ce", "watts_mean", "tokens_per_joule"] if c in full.columns]
    full[numeric_cols] = full.groupby(["model_key", "test_baseline"])[numeric_cols].transform(
        lambda x: x.rolling(60, min_periods=1).mean()
    )
    return full


def legend_handles(models, conditions):
    """Model colours then condition dashes, with no pseudo-header entries.

    The "Model" and "Condition" headers cost two of the four rows available
    below a 3.5 in figure. The caption says colour identifies the model and
    dash pattern the condition, which is where that belongs.
    """
    handles = [Line2D([0], [0], color=MODEL_STYLE[m]["color"], lw=2.4,
                      label=MODEL_STYLE[m]["label"]) for m in models]
    for c in conditions:
        st = CONDITION_STYLE[c]
        handles.append(Line2D([0], [0], color=INK_SECONDARY, lw=1.8,
                              linestyle=st["linestyle"], label=st["label"]))
    return handles


def _draw_inset(ax, sub, spec):
    """Magnify one model's band, where the interesting variation is too small
    to read against the full y range.

    Only used where the magnified difference is real. RAM deliberately has no
    inset: its spread across conditions is 25-37 MB against 13-39 MB of
    within-condition noise, so magnifying it would show five separated lines a
    reader would take for an effect of the frequency cap. It is allocator
    noise, and the paper's claim is that the footprint does not drift.
    """
    axins = ax.inset_axes(spec["box"])
    for cond in spec["conditions"]:
        g = sub[(sub.model_key == spec["model"]) & (sub.condition == cond)]
        if g.empty:
            continue
        for _b, gg in g.groupby("test_baseline"):
            gg = gg.sort_values("Time (Hours)")
            st = CONDITION_STYLE[cond]
            axins.plot(gg["Time (Hours)"], gg[spec["col"]],
                       color=MODEL_STYLE[spec["model"]]["color"],
                       linestyle=st["linestyle"], linewidth=st["lw"], zorder=st["z"])
    axins.set_xlim(*spec["xlim"])
    axins.set_ylim(*spec["ylim"])
    axins.tick_params(labelsize=5.5, length=2, pad=1)
    axins.grid(True, linewidth=0.4, alpha=0.6)
    for sp in ["top", "right"]:
        axins.spines[sp].set_visible(False)
    axins.set_facecolor(SURFACE)
    ax.indicate_inset_zoom(axins, edgecolor=INK_MUTED, linewidth=0.7, alpha=0.7)
    return axins


def plot_pair_metric(df, model_a, model_b, metric_col, metric_label, out_name,
                     conditions, inset=None):
    # \textwidth of a two-column IEEEtran page is 7.16 in. Generating at that
    # width and printing without reduction keeps the 9 pt labels at 9 pt; the
    # previous 13 in figure was reduced 3.7x into a single column, which put
    # its axis labels below 6 pt.
    fig, ax = plt.subplots(figsize=(3.5, 2.75))
    sub = df[df.model_key.isin([model_a, model_b]) & df.condition.isin(conditions)]
    for model_key in [model_a, model_b]:
        color = MODEL_STYLE[model_key]["color"]
        for cond in conditions:
            g = sub[(sub.model_key == model_key) & (sub.condition == cond)]
            if g.empty:
                continue
            for baseline, gg in g.groupby("test_baseline"):
                gg = gg.sort_values("Time (Hours)")
                st = CONDITION_STYLE[cond]
                ax.plot(gg["Time (Hours)"], gg[metric_col], color=color,
                        linestyle=st["linestyle"], linewidth=st["lw"], alpha=1.0, zorder=st["z"])

    ax.set_xlabel("Time (Hours)")
    ax.set_ylabel(metric_label)
    ax.grid(True, linewidth=0.8, alpha=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    # No in-figure title: the LaTeX caption carries it, and duplicating it here
    # cost vertical space that the y-axis label then collided with.

    # Legend below the axes rather than beside them. Beside, it consumed two
    # thirds of a 7.16 in canvas and squeezed the data into the remainder; the
    # side placement only worked on the 13 in figure this replaces.
    if inset:
        _draw_inset(ax, sub, inset)

    handles = legend_handles([model_a, model_b], conditions)
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.30),
              ncol=2, frameon=False, fontsize=6.5, labelcolor=INK_SECONDARY,
              columnspacing=1.0, handlelength=1.8, handletextpad=0.5,
              labelspacing=0.35, borderpad=0.0)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, f"{out_name}.pdf"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_name)


# Where a magnified band shows something the full range hides. Keyed by the
# figure's out_name suffix so the dispatch stays declarative.
INSETS = {
    "pair_qwen_phi3_00_reproducibility_R1_R2": {
        "model": "phi3_mini", "col": "decode_tps", "conditions": ["R1", "R2"],
        "box": [0.34, 0.30, 0.62, 0.32], "xlim": (0, 48), "ylim": (20.2, 24.4),
    },
    "pair_qwen_phi3_03_decode_tps": {
        "model": "phi3_mini", "col": "decode_tps", "conditions": ["R1"],
        "box": [0.34, 0.20, 0.62, 0.28], "xlim": (0, 48), "ylim": (20.2, 24.2),
    },
}


def plot_reproducibility(df, model_a, model_b, out_name):
    plot_pair_metric(df, model_a, model_b, "decode_tps", "Decode Throughput (tokens/s)",
                      out_name, conditions=["R1", "R2"],
                      inset=INSETS.get(out_name))


def plot_bar_summary(df, metric_col, ylabel, out_name):
    conditions = BAR_CONDITIONS
    models = list(MODEL_STYLE.keys())
    summary = df.groupby(["model_key", "condition"])[metric_col].mean().reset_index()

    fig, ax = plt.subplots(figsize=(3.5, 2.5))
    n_cond = len(conditions)
    width = 0.8 / n_cond
    x = range(len(models))
    for i, cond in enumerate(conditions):
        vals = []
        for m in models:
            row = summary[(summary.model_key == m) & (summary.condition == cond)]
            vals.append(row[metric_col].iloc[0] if not row.empty else 0)
        offsets = [xi + (i - n_cond / 2) * width + width / 2 for xi in x]
        ax.bar(offsets, vals, width=width * 0.92,
               color=CONDITION_BAR_COLOR[cond],
               edgecolor=INK_PRIMARY, linewidth=0.8,
               label=CONDITION_STYLE[cond]["label"])

    ax.set_xticks(list(x))
    wrapped_labels = [MODEL_STYLE[m]["label"].replace(" (", "\n(") for m in models]
    ax.set_xticklabels(wrapped_labels, rotation=0, ha="center", fontsize=8)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.8, alpha=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3,
              frameon=False, fontsize=6.5, labelcolor=INK_SECONDARY,
              columnspacing=1.0, handlelength=1.6, handletextpad=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, f"{out_name}.pdf"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_name)


def main():
    df = load_all()
    print("Loaded rows:", len(df))
    print(df.groupby(["model_key", "condition"]).size())

    for model_a, model_b, tag in PAIRS:
        for metric_col, metric_label, metric_tag in METRICS:
            name = f"{tag}_{metric_tag}"
            plot_pair_metric(df, model_a, model_b, metric_col, metric_label,
                              name, conditions=CONDITION_ORDER,
                              inset=INSETS.get(name))
        plot_reproducibility(df, model_a, model_b, f"{tag}_00_reproducibility_R1_R2")

    plot_bar_summary(df, "decode_tps", "Avg Decode Throughput (tokens/s)", "bar_01_decode_tps")
    plot_bar_summary(df, "watts_mean", "Avg Power Draw (W)", "bar_02_power")
    plot_bar_summary(df, "tokens_per_joule", "Avg Efficiency (Tokens/Joule)", "bar_03_efficiency")

    df.to_csv(os.path.join(OUT_DIR, "combined_dataset.csv"), index=False)
    print("Done.")


if __name__ == "__main__":
    main()
