#!/usr/bin/env python3
"""Single-panel cap-adherence figure, sized for the column it is printed in.

The manuscript version of this figure is a 2x2 grid drawn for the full text
width. Placed in one 88.9 mm column of the IoT-J paper it became four panels of
44 mm each, which is not a figure anyone reads. It does not need four panels:
the quantity plotted is already normalised per model -- prefill throughput as a
fraction of that model's own uncapped run -- so all four share one scale and
belong on one axes, exactly as the efficiency curve does.

It is sized the same way, too, which is the only way to get type right:

    effective pt = in-figure pt x (printed width / canvas width)

WHAT IT SHOWS. Prefill is compute-bound, so its throughput tracks clock rate.
Fitting that relation on campaigns whose frequency was verified gives an
expected value at any cap. The original 50% campaign sits far above its
expectation, which is how a run that had silently lost its cap was found.

ONE CORRECTION CARRIED FROM THE OLD FIGURE. Its caption said the fit used
"only the three verified scenarios (62.5/75/87.5%)". The code fits four,
100% included, and always did. The caption was wrong, not the fit.

Usage:
    python3 analysis_output/generate_cap_adherence_figure.py
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_threats_figure import (  # noqa: E402
    VALID_DIRS, R1_DIR, INVALID_50_DIR, NOMINAL_50_MHZ, MODEL_STYLE,
    CRITICAL_RED, BASELINE, prefill_mean,
)

GIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"

TARGET = dict(
    name="paper",
    out=os.path.join(GIT, "paper1-iotj", "fig", "cap_adherence.pdf"),
    printed_mm=88.9, w=5.4, h=4.85, ncol=2,
    pt=dict(base=12, tick=13, axis=14, legend=11.5),
    adjust=dict(left=0.185, right=0.965, top=0.97, bottom=0.32),
)


def render(t):
    PT = t["pt"]
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
        "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
        "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
        "font.family": "serif", "font.size": PT["base"],
    })
    fig, ax = plt.subplots(figsize=(t["w"], t["h"]))

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
        ax.scatter(xs, ys, color=style["color"], s=22, zorder=3)

        expected = slope * NOMINAL_50_MHZ + intercept
        observed = prefill_mean(INVALID_50_DIR, model_key) / r1
        ax.scatter([NOMINAL_50_MHZ], [expected], marker="o", s=34,
                   facecolor="white", edgecolor=style["color"],
                   linewidth=1.2, zorder=4)
        ax.scatter([NOMINAL_50_MHZ], [observed], marker="X", s=70,
                   color=CRITICAL_RED, edgecolor="white", linewidth=0.7, zorder=5)
        handles.append(line)
        print(f"  {style['label']:<18} expected {expected:.3f}  observed {observed:.3f}"
              f"  implied {(observed - intercept) / slope:.0f} MHz")

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
                   markeredgecolor=POSTER_SLATE, markersize=PT["legend"] - 4,
                   label="expected at 50 %"),
        plt.Line2D([0], [0], marker="X", color="none",
                   markerfacecolor=CRITICAL_RED, markeredgecolor="white",
                   markersize=PT["legend"] - 2, label="observed, original run"),
    ]
    fig.subplots_adjust(**t["adjust"])
    leg = fig.legend(handles=handles, loc="lower center", frameon=False,
                     ncol=t["ncol"], fontsize=PT["legend"], handletextpad=0.5,
                     columnspacing=1.4, labelspacing=0.4, borderaxespad=0.4)

    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    gap_in = (ax.xaxis.label.get_window_extent(renderer=r).y0
              - leg.get_window_extent(renderer=r).y1) / fig.dpi
    if gap_in <= 0:
        raise RuntimeError("x label and legend overlap")

    scale = (t["printed_mm"] / 25.4) / t["w"]
    os.makedirs(os.path.dirname(t["out"]), exist_ok=True)
    fig.savefig(t["out"], facecolor="white")
    plt.close(fig)
    print(f"\n  {t['printed_mm']:.1f} mm wide, canvas {t['w']}x{t['h']} in -> "
          f"scale {scale:.2f}, {PT['axis']} pt label prints at "
          f"{PT['axis']*scale:.1f} pt, label/legend gap {gap_in*25.4*scale:.1f} mm")
    print(f"  {t['out']}")


if __name__ == "__main__":
    render(TARGET)
