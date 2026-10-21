#!/usr/bin/env python3
"""The CAE2M figure: intra-model gains, design space, and grid siting comparison.

CE = T_J x 3.6e6 / CI_grid, in tokens per gram of CO2eq.

This figure compares the best and worst measured configurations for both
Qwen2.5 0.5B and Llama 3.1 8B, highlighting:
  1. The INTRA-MODEL gain achieved by frequency capping:
     - Qwen2.5 0.5B: 1.52x (+52%) between 75% cap and uncapped
     - Llama 3.1 8B: 1.74x (+74%) between 62.5% cap and uncapped
  2. The OVERALL DESIGN SPACE gap (models & caps):
     - 14.8x between absolute best (Qwen 75%) and worst (Llama uncapped)
  3. The SITING LEVER across grid intensities:
     - 14x from clean (50 gCO2eq/kWh) to coal-heavy (700 gCO2eq/kWh)

Usage:
    python3 analysis_output/generate_ce_figure.py
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_efficiency_curve_figure import (
    COMBINED_CSV, MODEL_STYLE, ORDER, BASELINE, CRITICAL_RED,
)

GIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"

J_PER_KWH = 3.6e6
CI_LO, CI_REF, CI_HI = 50.0, 400.0, 700.0

TARGET = dict(
    out=os.path.join(GIT, "paper1-iotj", "fig", "ce_metric.pdf"),
    printed_mm=88.9, w=5.4, h=4.6,
    pt=dict(base=11, tick=11.5, axis=12.5, legend=9.5, note=9.5),
    adjust=dict(left=0.19, right=0.965, top=0.97, bottom=0.28),
)


def main():
    t = TARGET
    PT = t["pt"]
    df = pd.read_csv(COMBINED_CSV,
                     usecols=["model_key", "condition", "tokens_per_joule"],
                     low_memory=False)
    tj = df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()

    qwen_best = tj[("qwen2.5_0.5b", "75")]
    qwen_worst = tj[("qwen2.5_0.5b", "R1")]
    llama_best = tj[("llama3.1_8b", "62_5")]
    llama_worst = tj[("llama3.1_8b", "R1")]

    q_gain = qwen_best / qwen_worst
    l_gain = llama_best / llama_worst
    total_ratio = qwen_best / llama_worst
    grid_ratio = CI_HI / CI_LO

    print(f"  Qwen2.5 0.5B: best(75%)={qwen_best:.4f}, worst(R1)={qwen_worst:.4f} -> {q_gain:.3f}x (+{(q_gain-1)*100:.1f}%)")
    print(f"  Llama 3.1 8B: best(62.5%)={llama_best:.4f}, worst(R1)={llama_worst:.4f} -> {l_gain:.3f}x (+{(l_gain-1)*100:.1f}%)")
    print(f"  Design-space span {total_ratio:.1f}x, grid span {grid_ratio:.0f}x")

    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
        "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
        "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
        "font.family": "serif", "font.size": PT["base"],
    })
    fig, ax = plt.subplots(figsize=(t["w"], t["h"]))

    ci = np.linspace(CI_LO, CI_HI, 200)
    q_col = MODEL_STYLE["qwen2.5_0.5b"]["color"]
    l_col = MODEL_STYLE["llama3.1_8b"]["color"]

    # Plot curves: best (solid) and worst (dashed) for both models
    ax.plot(ci, qwen_best * J_PER_KWH / ci, color=q_col, linewidth=1.8,
            zorder=3, label="Qwen2.5: best (75% cap)")
    ax.plot(ci, qwen_worst * J_PER_KWH / ci, color=q_col, linewidth=1.4,
            linestyle="--", zorder=3, label="Qwen2.5: worst (uncapped)")

    ax.plot(ci, llama_best * J_PER_KWH / ci, color=l_col, linewidth=1.8,
            zorder=3, label="Llama 3.1: best (62.5% cap)")
    ax.plot(ci, llama_worst * J_PER_KWH / ci, color=l_col, linewidth=1.4,
            linestyle="--", zorder=3, label="Llama 3.1: worst (uncapped)")

    # Shaded intra-model bands
    ax.fill_between(ci, qwen_worst * J_PER_KWH / ci, qwen_best * J_PER_KWH / ci,
                    color=q_col, alpha=0.10, zorder=2)
    ax.fill_between(ci, llama_worst * J_PER_KWH / ci, llama_best * J_PER_KWH / ci,
                    color=l_col, alpha=0.10, zorder=2)

    ax.set_yscale("log")
    ax.set_xlim(CI_LO - 15, CI_HI + 15)
    ax.set_ylim(280, 1.4e5)

    # 1. Intra-model comparison for Qwen: arrow at CI = 120, badge to the right
    xq = 120
    yq_hi = qwen_best * J_PER_KWH / xq
    yq_lo = qwen_worst * J_PER_KWH / xq
    ax.annotate("", xy=(xq, yq_hi), xytext=(xq, yq_lo),
                arrowprops=dict(arrowstyle="<->", color=q_col, lw=1.3), zorder=4)
    ax.annotate(f"intra-Qwen\n+{ (q_gain-1)*100:.0f}% ({q_gain:.2f}$\\times$)",
                xy=(xq, (yq_hi * yq_lo)**0.5), xytext=(12, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=8.0, color=q_col, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=q_col, lw=0.7, alpha=0.95))

    # 2. Intra-model comparison for Llama: arrow at CI = 120, badge to the right
    xl = 120
    yl_hi = llama_best * J_PER_KWH / xl
    yl_lo = llama_worst * J_PER_KWH / xl
    ax.annotate("", xy=(xl, yl_hi), xytext=(xl, yl_lo),
                arrowprops=dict(arrowstyle="<->", color=l_col, lw=1.3), zorder=4)
    ax.annotate(f"intra-Llama\n+{ (l_gain-1)*100:.0f}% ({l_gain:.2f}$\\times$)",
                xy=(xl, (yl_hi * yl_lo)**0.5), xytext=(12, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=8.0, color=l_col, fontweight="bold", zorder=5,
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=l_col, lw=0.7, alpha=0.95))

    # 3. Overall design space gap: between Llama worst and Qwen best at CI_REF = 400
    xb = CI_REF
    yb_hi = qwen_best * J_PER_KWH / xb
    yb_lo = llama_worst * J_PER_KWH / xb
    ax.annotate("", xy=(xb, yb_hi), xytext=(xb, yb_lo),
                arrowprops=dict(arrowstyle="<->", color=POSTER_INK, lw=1.2), zorder=4)
    ax.annotate(f"models & caps\n{total_ratio:.1f}$\\times$",
                xy=(xb, (yb_hi * yb_lo) ** 0.5), xytext=(10, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=8.5, color=POSTER_INK, zorder=5,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#c3c2b7", lw=0.6, alpha=0.95))

    # 4. Siting, as a vertical distance along the worst curve on the right
    xg_lo, xg_hi = CI_LO, CI_HI
    ax.annotate("", xy=(xg_hi, llama_worst * J_PER_KWH / xg_lo),
                xytext=(xg_hi, llama_worst * J_PER_KWH / xg_hi),
                arrowprops=dict(arrowstyle="<->", color=CRITICAL_RED, lw=1.2), zorder=4)
    ax.annotate(f"grid\n{grid_ratio:.0f}$\\times$",
                xy=(xg_hi, llama_worst * J_PER_KWH / (xg_lo * xg_hi) ** 0.5),
                xytext=(-8, 0), textcoords="offset points", ha="right",
                va="center", fontsize=PT["note"], color=CRITICAL_RED, zorder=5)
    ax.plot([xg_lo, xg_hi], [llama_worst * J_PER_KWH / xg_lo] * 2,
            color=CRITICAL_RED, linewidth=0.8, linestyle=(0, (2, 2)), zorder=2)

    for x in (CI_LO, CI_REF, CI_HI):
        ax.axvline(x, color=BASELINE, linewidth=0.8, linestyle=(0, (1, 3)), zorder=1)

    ax.set_xticks([CI_LO, CI_REF, CI_HI])
    ax.set_xticklabels([f"{int(CI_LO)}\nclean", f"{int(CI_REF)}\nmixed", f"{int(CI_HI)}\ncoal-heavy"])
    ax.tick_params(axis="both", labelsize=PT["tick"])
    ax.set_xlabel("Grid carbon intensity (gCO$_2$eq/kWh)", fontsize=PT["axis"], labelpad=6)
    ax.set_ylabel("$CE$ (tokens per gCO$_2$eq)", fontsize=PT["axis"], labelpad=5)
    ax.grid(True, axis="y", which="major", linewidth=0.6, alpha=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    scale = (t["printed_mm"] / 25.4) / t["w"]
    fig.subplots_adjust(**t["adjust"])
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    xl_y0_fig = ax.xaxis.label.get_window_extent(renderer=r).y0 / fig.bbox.height
    desired_gap_mm = 2.0
    gap_fig = (desired_gap_mm / 25.4 / scale) / t["h"]

    leg = fig.legend(loc="upper center", bbox_to_anchor=(0.58, xl_y0_fig - gap_fig),
                     frameon=False, ncol=2, fontsize=PT["legend"],
                     handletextpad=0.5, columnspacing=1.0, labelspacing=0.35, borderaxespad=0.2)

    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    gap_in = (ax.xaxis.label.get_window_extent(renderer=r).y0
              - leg.get_window_extent(renderer=r).y1) / fig.dpi
    if gap_in <= 0:
        raise RuntimeError("x label and legend overlap")

    os.makedirs(os.path.dirname(t["out"]), exist_ok=True)
    fig.savefig(t["out"], facecolor="white")
    png_out = os.path.splitext(t["out"])[0] + ".png"
    fig.savefig(png_out, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"\n  {t['printed_mm']:.1f} mm wide -> scale {scale:.2f}, "
          f"{PT['axis']} pt label prints at {PT['axis']*scale:.1f} pt, "
          f"label/legend gap {gap_in*25.4*scale:.1f} mm")
    print(f"  {t['out']}")


if __name__ == "__main__":
    main()
