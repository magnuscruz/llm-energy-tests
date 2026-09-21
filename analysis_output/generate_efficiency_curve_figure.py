import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = os.path.dirname(__file__)
COMBINED_CSV = os.path.join(OUT_DIR, "combined_dataset.csv.gz")

MODEL_STYLE = {
    "llama3.1_8b":      {"label": "Llama 3.1 8B",       "color": "#2a78d6"},
    "deepseek-v2_lite": {"label": "DeepSeek-v2 Lite",    "color": "#eb6834"},
    "qwen2.5_0.5b":     {"label": "Qwen2.5 0.5B",        "color": "#1baf7a"},
    "phi3_mini":        {"label": "Phi-3 Mini",          "color": "#eda100"},
}

# Cap ladder expressed in absolute MHz, consistent with methodology/index.tex
# Section III-B: caps are defined relative to the 3.5GHz (3500 MHz) E-core
# maximum. R1 used to be drawn AT 3500, on the reasoning that an uncapped run
# sits at the 100% point of that scale. That is now wrong twice over: the 100%
# campaign is an actual measurement at a 3500 MHz cap, so the x-position is
# taken, and an uncapped run does not sit there anyway -- with turbo free it
# sustains ~4.1 GHz. R1 predates frequency telemetry, so its x-position is the
# mean sustained frequency measured in R3, the unthrottled campaign that does
# carry per-core logging (4.01-4.21 GHz across the four models).
CONDITION_MHZ = {
    "R1": 4100, "100": 3500, "87_5": 3063, "75": 2625, "62_5": 2188, "50": 1750,
}
CONDITION_LABEL = {
    "R1": "R1\n(turbo)", "100": "100%", "87_5": "87.5%", "75": "75%", "62_5": "62.5%", "50": "50%",
}
ORDER = ["50", "62_5", "75", "87_5", "100", "R1"]  # left-to-right, ascending MHz

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


def load_tj_by_condition():
    df = pd.read_csv(COMBINED_CSV, usecols=["model_key", "condition", "tokens_per_joule"], low_memory=False)
    return df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()


def main():
    tj = load_tj_by_condition()

    fig, axes = plt.subplots(2, 2, figsize=(9, 7.2), sharex=True)
    axes = axes.flatten()

    for ax, (model_key, style) in zip(axes, MODEL_STYLE.items()):
        xs = [CONDITION_MHZ[c] for c in ORDER]
        ys = [tj[(model_key, c)] for c in ORDER]
        peak_i = ys.index(max(ys))

        ax.plot(xs, ys, color=style["color"], linewidth=1.6, marker="o", markersize=6, zorder=2)
        ax.scatter([xs[peak_i]], [ys[peak_i]], marker="*", s=220, color=CRITICAL_RED,
                   edgecolor=INK_PRIMARY, linewidth=0.5, zorder=4, label="Peak $T_J$")
        # Shade the empirically-optimal 62.5-75% band common across all four models
        ax.axvspan(CONDITION_MHZ["75"], CONDITION_MHZ["62_5"], color=INK_SECONDARY, alpha=0.08, zorder=1)

        ax.set_xticks(xs)
        ax.set_xticklabels([CONDITION_LABEL[c] for c in ORDER], fontsize=8)
        ax.set_title(style["label"], fontsize=10.5, color=INK_PRIMARY)
        ax.grid(True, linewidth=0.6, alpha=0.8)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ymax = max(ys)
        ax.set_ylim(0, ymax * 1.25)

    for ax in axes[2:]:
        ax.set_xlabel("Throttling Condition")
    for ax in [axes[0], axes[2]]:
        ax.set_ylabel("Tokens per Joule ($T_J$)")

    handles = [
        plt.Line2D([0], [0], color=INK_SECONDARY, lw=1.6, marker="o", markersize=6, label="Mean $T_J$ by condition"),
        plt.Line2D([0], [0], color="none", marker="*", markersize=14, markerfacecolor=CRITICAL_RED,
                   markeredgecolor=INK_PRIMARY, label="Peak $T_J$"),
        plt.Rectangle((0, 0), 1, 1, color=INK_SECONDARY, alpha=0.15, label="62.5–75% band"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.03), ncol=3, frameon=False, fontsize=8.5)
    fig.suptitle("Eco-Efficiency vs. CPU Frequency Cap, by Model", fontsize=11.5, y=0.995)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "efficiency_vs_cap.pdf"), facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("wrote efficiency_vs_cap.pdf")

    for model_key in MODEL_STYLE:
        vals = {c: round(tj[(model_key, c)], 3) for c in ORDER}
        print(model_key, vals)


if __name__ == "__main__":
    main()
