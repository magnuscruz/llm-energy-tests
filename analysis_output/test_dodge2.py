import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_threats_figure import (
    VALID_DIRS, R1_DIR, INVALID_50_DIR, NOMINAL_50_MHZ, MODEL_STYLE,
    CRITICAL_RED, BASELINE, prefill_mean,
)

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
VERIFIED_50_DIR = f"{LOGS_DIR}/2026-07-19_48h_50_throttling/deep_aging"

PT = dict(base=12, tick=13, axis=14, legend=11)
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": BASELINE, "axes.labelcolor": "#1B2A3A",
    "text.color": "#1B2A3A", "xtick.color": "#41566B",
    "ytick.color": "#41566B", "grid.color": "#e1e0d9",
    "font.family": "serif", "font.size": PT["base"],
})

fig, ax = plt.subplots(figsize=(5.4, 5.1))
xs = np.array([mhz for _, mhz in VALID_DIRS.values()], dtype=float)
handles = []

for model_key, style in MODEL_STYLE.items():
    r1 = prefill_mean(R1_DIR, model_key)
    ys = np.array([prefill_mean(d, model_key) / r1 for d, _ in VALID_DIRS.values()])
    slope, intercept = np.polyfit(xs, ys, 1)

    fit_x = np.linspace(NOMINAL_50_MHZ, xs.max(), 100)
    fit_y = slope * fit_x + intercept
    solid = fit_x >= xs.min()
    line, = ax.plot(fit_x[solid], fit_y[solid], color=style["color"],
                    linewidth=1.5, zorder=2, label=style["label"])
    ax.plot(fit_x[~solid], fit_y[~solid], color=style["color"],
            linewidth=1.2, linestyle=(0, (2, 2)), zorder=2)
    ax.scatter(xs, ys, color=style["color"], s=26, zorder=3)

    expected = slope * NOMINAL_50_MHZ + intercept
    observed_inv = prefill_mean(INVALID_50_DIR, model_key) / r1
    observed_ver = prefill_mean(VERIFIED_50_DIR, model_key) / r1

    # Expected hollow circle at 1750
    ax.scatter([NOMINAL_50_MHZ], [expected], marker="o", s=38,
               facecolor="white", edgecolor=style["color"],
               linewidth=1.3, zorder=4)
    # Verified 50% (without turbo) at 1750 - solid circle with thin white edge
    ax.scatter([NOMINAL_50_MHZ], [observed_ver], marker="o", s=28,
               color=style["color"], edgecolor="white", linewidth=0.6, zorder=5)
    # Invalid 50% (with turbo) - red cross, slight offset +22 MHz so it never obscures any verified 50% dot
    ax.scatter([NOMINAL_50_MHZ + 22], [observed_inv], marker="X", s=68,
               color=CRITICAL_RED, edgecolor="white", linewidth=0.7, zorder=6)

    handles.append(line)

ax.set_xticks([NOMINAL_50_MHZ] + list(xs))
ax.set_xticklabels(["1750"] + [f"{int(v)}" for v in xs], fontsize=PT["tick"])
ax.tick_params(axis="y", labelsize=PT["tick"])
ax.set_xlabel("Nominal frequency cap (MHz)", fontsize=PT["axis"], labelpad=6)
ax.set_ylabel("Prefill throughput\n(fraction of uncapped)",
              fontsize=PT["axis"], labelpad=5)
ax.grid(True, axis="y", linewidth=0.6, alpha=0.7)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
ax.set_xlim(NOMINAL_50_MHZ - 120, xs.max() + 120)

handles += [
    plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="white",
               markeredgecolor="#41566B", markersize=PT["legend"] - 4,
               label="expected at 50 %"),
    plt.Line2D([0], [0], marker="X", color="none",
               markerfacecolor=CRITICAL_RED, markeredgecolor="white",
               markersize=PT["legend"] - 2, label="50 % with turbo (original)"),
    plt.Line2D([0], [0], marker="o", color="none",
               markerfacecolor="#41566B", markeredgecolor="white",
               markersize=PT["legend"] - 4, label="50 % without turbo (verified)"),
]

fig.subplots_adjust(left=0.185, right=0.965, top=0.97, bottom=0.34)
leg = fig.legend(handles=handles, loc="lower center", frameon=False,
                 ncol=2, fontsize=PT["legend"], handletextpad=0.5,
                 columnspacing=1.2, labelspacing=0.35, borderaxespad=0.2)

fig.savefig("analysis_output/test_dodge2.png", dpi=200, facecolor="white")
plt.close(fig)
print("Saved dodge2")
