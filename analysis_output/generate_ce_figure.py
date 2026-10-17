#!/usr/bin/env python3
"""The CAE2M figure: what the grid is worth against what the design space is.

CE = T_J x 3.6e6 / CI_grid, in tokens per gram of CO2eq. Because CI_grid is a
divisor, it rescales every configuration by the same factor and cannot reorder
them -- so a figure that simply plots CE per model would say nothing the
tokens-per-joule table does not already say.

What is worth drawing is the comparison the section makes, and drawing it is
also what keeps it honest. On a log axis the two spreads are two distances:

  * the VERTICAL GAP between the best and worst measured configuration, at any
    fixed grid, is the whole design space of models and frequency caps;
  * the VERTICAL TRAVEL along either curve, from a clean grid to a coal-heavy
    one, is what siting alone is worth.

They come out of the same order, 14.8x against 14x, which is the section's
point and is weaker than the claim this project carried for a while -- that
the grid "exceeds" the design space. It does not: 14 is less than 14.8. The
figure makes the two distances comparable by eye, so the overstatement cannot
return unnoticed.

The grid interval is stated, not chosen to flatter: 50 to 700 gCO2eq/kWh, the
same values the text uses.

Usage:
    python3 analysis_output/generate_ce_figure.py
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

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
    printed_mm=88.9, w=5.4, h=4.85,
    pt=dict(base=12, tick=13, axis=14, legend=11.5, note=11),
    adjust=dict(left=0.215, right=0.895, top=0.97, bottom=0.345),
)


def main():
    t = TARGET
    PT = t["pt"]
    df = pd.read_csv(COMBINED_CSV,
                     usecols=["model_key", "condition", "tokens_per_joule"],
                     low_memory=False)
    tj = df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()
    cells = {(m, c): tj[(m, c)] for m in MODEL_STYLE for c in ORDER}
    (bm, bc), best = max(cells.items(), key=lambda kv: kv[1])
    (wm, wc), worst = min(cells.items(), key=lambda kv: kv[1])
    print(f"  best  {MODEL_STYLE[bm]['label']} at {bc}: T_J = {best:.4f}")
    print(f"  worst {MODEL_STYLE[wm]['label']} at {wc}: T_J = {worst:.4f}")
    print(f"  design-space spread {best/worst:.1f}x, grid spread {CI_HI/CI_LO:.0f}x")

    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
        "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
        "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
        "font.family": "serif", "font.size": PT["base"],
    })
    fig, ax = plt.subplots(figsize=(t["w"], t["h"]))

    ci = np.linspace(CI_LO, CI_HI, 200)
    for tjv, label, colour in ((best, "best measured configuration",
                                MODEL_STYLE[bm]["color"]),
                               (worst, "worst measured configuration",
                                MODEL_STYLE[wm]["color"])):
        ax.plot(ci, tjv * J_PER_KWH / ci, color=colour, linewidth=1.8,
                zorder=3, label=label)

    ax.set_yscale("log")
    ax.set_xlim(CI_LO - 15, CI_HI + 15)

    # The design space, as a vertical distance at the reference grid.
    xb = CI_REF
    yb_hi, yb_lo = best * J_PER_KWH / xb, worst * J_PER_KWH / xb
    ax.annotate("", xy=(xb, yb_hi), xytext=(xb, yb_lo),
                arrowprops=dict(arrowstyle="<->", color=POSTER_INK, lw=1.2))
    ax.annotate(f"models and caps\n{best/worst:.1f}$\\times$",
                xy=(xb, (yb_hi * yb_lo) ** 0.5), xytext=(10, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=PT["note"], color=POSTER_INK)

    # Siting, as a vertical distance along the worst curve.
    xg_lo, xg_hi = CI_LO, CI_HI
    ax.annotate("", xy=(xg_hi, worst * J_PER_KWH / xg_lo),
                xytext=(xg_hi, worst * J_PER_KWH / xg_hi),
                arrowprops=dict(arrowstyle="<->", color=CRITICAL_RED, lw=1.2))
    ax.annotate(f"grid\n{CI_HI/CI_LO:.0f}$\\times$",
                xy=(xg_hi, worst * J_PER_KWH / (xg_lo * xg_hi) ** 0.5),
                xytext=(-8, 0), textcoords="offset points", ha="right",
                va="center", fontsize=PT["note"], color=CRITICAL_RED)
    ax.plot([xg_lo, xg_hi], [worst * J_PER_KWH / xg_lo] * 2,
            color=CRITICAL_RED, linewidth=0.8, linestyle=(0, (2, 2)), zorder=2)

    for x in (CI_LO, CI_REF, CI_HI):
        ax.axvline(x, color=BASELINE, linewidth=0.8, linestyle=(0, (1, 3)),
                   zorder=1)

    # The three reference grids are named under their own ticks. Set beside the
    # lines instead, rotated, they landed on the arrows and on each other.
    ax.set_xticks([CI_LO, CI_REF, CI_HI])
    ax.set_xticklabels([f"{int(CI_LO)}\nclean", f"{int(CI_REF)}\nmixed",
                        f"{int(CI_HI)}\ncoal-heavy"])
    ax.tick_params(axis="both", labelsize=PT["tick"])
    ax.set_xlabel("Grid carbon intensity (gCO$_2$eq/kWh)",
                  fontsize=PT["axis"], labelpad=6)
    ax.set_ylabel("$CE$ (tokens per gCO$_2$eq)", fontsize=PT["axis"], labelpad=5)
    ax.grid(True, axis="y", which="major", linewidth=0.6, alpha=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.subplots_adjust(**t["adjust"])
    leg = fig.legend(loc="lower center", frameon=False, ncol=1,
                     fontsize=PT["legend"], handletextpad=0.6,
                     labelspacing=0.4, borderaxespad=0.4)

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
    print(f"\n  {t['printed_mm']:.1f} mm wide -> scale {scale:.2f}, "
          f"{PT['axis']} pt label prints at {PT['axis']*scale:.1f} pt, "
          f"label/legend gap {gap_in*25.4*scale:.1f} mm")
    print(f"  {t['out']}")


if __name__ == "__main__":
    main()
