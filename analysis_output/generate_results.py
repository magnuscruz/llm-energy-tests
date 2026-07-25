import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
OUT_DIR = os.path.dirname(__file__)

# The 50% campaign currently on disk (logs/2026-07-11_48h_50_throttling) is the
# pre-hardened-protocol run: effective frequency ~2.4GHz vs the 1.75GHz cap ladder
# (see threats/index.tex in IEEETransactions). Excluded here, same as the paper.
EXCLUDED_BASELINES = {"48h_50_throttling"}

MODEL_STYLE = {
    "llama3.1_8b":      {"label": "Llama 3.1 8B (Dense)",       "color": "#2a78d6"},
    "deepseek-v2_lite": {"label": "DeepSeek-v2 Lite (MoE)",     "color": "#eb6834"},
    "qwen2.5_0.5b":     {"label": "Qwen2.5 0.5B (Dense)",       "color": "#1baf7a"},
    "phi3_mini":        {"label": "Phi-3 Mini (Dense)",         "color": "#eda100"},
}

CONDITION_STYLE = {
    "R1":     {"label": "R1 (Unthrottled)",       "linestyle": "solid",             "lw": 1.6, "z": 5},
    "R2":     {"label": "R2 (Unthrottled, rep.)", "linestyle": (0, (6, 2)),          "lw": 1.3, "z": 4},
    "87_5":   {"label": "Throttled 87.5%",        "linestyle": (0, (1, 1)),          "lw": 1.4, "z": 3},
    "75":     {"label": "Throttled 75%",          "linestyle": (0, (3, 1, 1, 1)),    "lw": 1.4, "z": 2},
    "62_5":   {"label": "Throttled 62.5%",        "linestyle": (0, (5, 5)),          "lw": 1.4, "z": 1},
}
CONDITION_ORDER = ["R1", "R2", "87_5", "75", "62_5"]

# Ordinal sequential ramp (one hue, light->dark), validated with
# scripts/validate_palette.js --ordinal (dataviz skill, palette.md).
CONDITION_BAR_COLOR = {
    "R1":    "#86b6ef",
    "R2":    "#5598e7",
    "87_5":  "#2a78d6",
    "75":    "#1c5cab",
    "62_5":  "#104281",
}

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
    "font.size": 10,
})


def parse_condition(test_baseline):
    for key in CONDITION_ORDER:
        marker = f"_{key}_" if key not in ("R1", "R2") else f"_{key}_"
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
        current_dir = os.path.dirname(f)
        for _ in range(5):
            dir_basename = os.path.basename(current_dir)
            if dir_basename and "_" in dir_basename and any(c.isdigit() for c in dir_basename.split("_")[0]):
                test_baseline = "_".join(dir_basename.split("_")[1:])
                break
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
        if test_baseline in EXCLUDED_BASELINES:
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
    handles = [Line2D([0], [0], color="none", label="Model")]
    for m in models:
        handles.append(Line2D([0], [0], color=MODEL_STYLE[m]["color"], lw=3, label=MODEL_STYLE[m]["label"]))
    handles.append(Line2D([0], [0], color="none", label=""))
    handles.append(Line2D([0], [0], color="none", label="Condition"))
    for c in conditions:
        st = CONDITION_STYLE[c]
        handles.append(Line2D([0], [0], color=INK_SECONDARY, lw=1.6, linestyle=st["linestyle"], label=st["label"]))
    return handles


def plot_pair_metric(df, model_a, model_b, metric_col, metric_label, out_name, conditions):
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
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
                        linestyle=st["linestyle"], linewidth=st["lw"], alpha=0.95, zorder=st["z"])

    ax.set_xlabel("Time (Hours)")
    ax.set_ylabel(metric_label)
    ax.grid(True, linewidth=0.6, alpha=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    title = f"{MODEL_STYLE[model_a]['label']} vs {MODEL_STYLE[model_b]['label']} — {metric_label}"
    ax.set_title(title, fontsize=12, color=INK_PRIMARY, pad=12)

    handles = legend_handles([model_a, model_b], conditions)
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=False, fontsize=8.5, labelcolor=INK_SECONDARY)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, f"{out_name}.png"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_name)


def plot_reproducibility(df, model_a, model_b, out_name):
    plot_pair_metric(df, model_a, model_b, "decode_tps", "Decode Throughput (tokens/s)",
                      out_name, conditions=["R1", "R2"])


def plot_bar_summary(df, metric_col, ylabel, out_name):
    conditions = ["R1", "R2", "87_5", "75", "62_5"]
    models = list(MODEL_STYLE.keys())
    summary = df.groupby(["model_key", "condition"])[metric_col].mean().reset_index()

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
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
               edgecolor=INK_PRIMARY, linewidth=0.4,
               label=CONDITION_STYLE[cond]["label"])

    ax.set_xticks(list(x))
    ax.set_xticklabels([MODEL_STYLE[m]["label"] for m in models], rotation=0, fontsize=9)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", linewidth=0.6, alpha=0.8)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.set_title(ylabel, fontsize=12, color=INK_PRIMARY, pad=12)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=8.5, labelcolor=INK_SECONDARY)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, f"{out_name}.png"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_name)


def main():
    df = load_all()
    print("Loaded rows:", len(df))
    print(df.groupby(["model_key", "condition"]).size())

    for model_a, model_b, tag in PAIRS:
        for metric_col, metric_label, metric_tag in METRICS:
            plot_pair_metric(df, model_a, model_b, metric_col, metric_label,
                              f"{tag}_{metric_tag}", conditions=CONDITION_ORDER)
        plot_reproducibility(df, model_a, model_b, f"{tag}_00_reproducibility_R1_R2")

    plot_bar_summary(df, "decode_tps", "Avg Decode Throughput (tokens/s)", "bar_01_decode_tps")
    plot_bar_summary(df, "watts_mean", "Avg Power Draw (W)", "bar_02_power")
    plot_bar_summary(df, "tokens_per_joule", "Avg Efficiency (Tokens/Joule)", "bar_03_efficiency")

    df.to_csv(os.path.join(OUT_DIR, "combined_dataset.csv"), index=False)
    print("Done.")


if __name__ == "__main__":
    main()
