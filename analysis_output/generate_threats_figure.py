import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
OUT_DIR = os.path.dirname(__file__)

VALID_DIRS = {
    "62.5%": (f"{LOGS_DIR}/2026-07-02_48h_62_5_throttling/deep_aging", 2188),
    "75%":   (f"{LOGS_DIR}/2026-06-14_48h_75_throttling/deep_aging", 2625),
    "87.5%": (f"{LOGS_DIR}/2026-08-18_48h_87_5_throttling/deep_aging", 3063),
    "100%":  (f"{LOGS_DIR}/2026-08-29_48h_100_throttling/deep_aging", 3500),
}
R1_DIR = f"{LOGS_DIR}/2026-05-09_48h_R2_no_throtting/deep_aging"
INVALID_50_DIR = f"{LOGS_DIR}/2026-07-11_48h_50_throttling/deep_aging"
NOMINAL_50_MHZ = 1750

MODEL_STYLE = {
    "llama3.1_8b":      {"label": "Llama 3.1 8B",       "color": "#2a78d6"},
    "deepseek-v2_lite": {"label": "DeepSeek-v2 Lite",    "color": "#eb6834"},
    "qwen2.5_0.5b":     {"label": "Qwen2.5 0.5B",        "color": "#1baf7a"},
    "phi3_mini":        {"label": "Phi-3 Mini",          "color": "#eda100"},
}
CRITICAL_RED = "#d03b3b"

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE, "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY, "xtick.color": INK_MUTED, "ytick.color": INK_MUTED,
    "grid.color": GRID, "font.family": "sans-serif", "font.size": 10,
})
# This figure is reproduced at full \textwidth (figure*, spanning both columns)
# in the paper. If it is ever switched to single-column width instead, double
# these font/line/marker sizes to stay legible after the shrink.


def prefill_mean(directory, model_key):
    df = pd.read_csv(f"{directory}/{model_key}_48.00h_merged_analysis.csv", low_memory=False)
    return df["prefill_tps"].dropna().iloc[1:].mean()


def main():
    fig, axes = plt.subplots(2, 2, figsize=(9, 7.2), dpi=150, sharex=True)
    axes = axes.flatten()
    table_rows = []

    for ax, (model_key, style) in zip(axes, MODEL_STYLE.items()):
        r1 = prefill_mean(R1_DIR, model_key)
        xs = np.array([mhz for _, mhz in VALID_DIRS.values()], dtype=float)
        ys = np.array([prefill_mean(d, model_key) / r1 for d, _ in VALID_DIRS.values()])
        slope, intercept = np.polyfit(xs, ys, 1)

        fit_x = np.linspace(NOMINAL_50_MHZ, 3063, 100)
        fit_y = slope * fit_x + intercept
        ax.plot(fit_x, fit_y, color=style["color"], linewidth=1.6, zorder=2)
        ax.plot(fit_x[fit_x <= 2188], fit_y[fit_x <= 2188], color=style["color"],
                linewidth=1.2, linestyle=(0, (2, 2)), zorder=2)
        ax.scatter(xs, ys, color=style["color"], s=42, zorder=3, edgecolor=INK_PRIMARY, linewidth=0.5)

        expected = slope * NOMINAL_50_MHZ + intercept
        observed = prefill_mean(INVALID_50_DIR, model_key) / r1
        implied_mhz = (observed - intercept) / slope

        ax.scatter([NOMINAL_50_MHZ], [expected], marker="o", s=42, facecolor="none",
                   edgecolor=style["color"], linewidth=1.3, zorder=3)
        ax.scatter([NOMINAL_50_MHZ], [observed], marker="X", s=90, color=CRITICAL_RED,
                   zorder=4, edgecolor=INK_PRIMARY, linewidth=0.5)
        ax.annotate("original\n50% run", (NOMINAL_50_MHZ, observed), xytext=(8, -4),
                    textcoords="offset points", fontsize=7.5, color=CRITICAL_RED)

        ax.set_title(style["label"], fontsize=10.5, color=INK_PRIMARY)
        ax.grid(True, linewidth=0.6, alpha=0.8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.set_ylim(0.3, 1.05)

        table_rows.append((style["label"], expected, observed, implied_mhz))

    for ax in axes[2:]:
        ax.set_xlabel("CPU Frequency Cap (MHz)")
    for ax in [axes[0], axes[2]]:
        ax.set_ylabel("Prefill TPS\n(fraction of R1)")

    handles = [
        plt.Line2D([0], [0], color=INK_SECONDARY, lw=1.6, label="Fit through verified conditions (62.5/75/87.5%)"),
        plt.Line2D([0], [0], color=INK_SECONDARY, lw=1.6, linestyle=(0, (2, 2)), label="Extrapolation to nominal 50% cap"),
        plt.Line2D([0], [0], marker="o", color="none", markeredgecolor=INK_SECONDARY, markersize=7, label="Expected (if cap honored)"),
        plt.Line2D([0], [0], marker="X", color=CRITICAL_RED, markersize=9, linewidth=0, label="Observed (original 50% campaign)"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=8.5)
    fig.suptitle("Detecting the Mis-Throttled 50% Campaign via a Compute-Bound Proxy", fontsize=11.5, y=0.995)
    fig.tight_layout(rect=[0, 0.06, 1, 0.97])
    fig.savefig(os.path.join(OUT_DIR, "threats_mis_throttle_detection.pdf"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)

    print(f"{'Model':18s} {'Expected@1750':>14s} {'Observed':>10s} {'Implied MHz':>12s}")
    for label, expected, observed, implied_mhz in table_rows:
        print(f"{label:18s} {expected:14.3f} {observed:10.3f} {implied_mhz:12.0f}")


if __name__ == "__main__":
    main()
