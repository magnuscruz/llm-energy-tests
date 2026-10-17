#!/usr/bin/env python3
"""Single-panel version of the efficiency curve, for the A2 poster.

The manuscript's figure is a 2x2 grid, one model per panel, in absolute tokens
per joule. That is right for a page the reader holds: the absolute values are
the measurement, and the 8.5x spread between best and worst model is itself a
result. On a poster read from two metres it fails, because four panels at half
a column width leave each curve a few centimetres across.

So this draws one axes with all four models, and the price of that is the y
axis. Absolute T_J cannot share an axis across an 8.5x spread without flattening
three of the four curves into the baseline. The curves are therefore normalised
to each model's own uncapped run, which is not a cosmetic choice: the poster's
claim is that *every* model gains when the clock is capped, and normalising to
uncapped is exactly that claim drawn. The absolute values stay in the paper,
and the model-choice spread is stated in the poster's text instead.

Reads the same smoothed combined dataset as the manuscript figure, so the two
cannot disagree about shape. Writes straight into the poster directory; it is
not part of install_paper_figures.py, because nothing in the manuscript
includes it.

Usage:
    python3 analysis_output/generate_poster_efficiency_figure.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from generate_efficiency_curve_figure import (
    COMBINED_CSV, CONDITION_MHZ, CONDITION_LABEL, ORDER, MODEL_STYLE,
    SURFACE, INK_PRIMARY, INK_SECONDARY, INK_MUTED, BASELINE, CRITICAL_RED,
)

GIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# The poster's own palette, so the figure does not arrive from a different
# document. ink/slate/accent are the three colours main.tex defines.
POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"
POSTER_ACCENT = "#C2552E"

# ONE DESIGN, TWO SIZES. The same figure goes on an A2 poster column of
# 116.8 mm and across the 181.9 mm text width of a two-column IEEE paper, and
# the body text beside it is 21.5 pt in one place and 10 pt in the other. A
# single file cannot serve both: a label is printed at
#
#     effective pt = in-figure pt x (printed width / canvas width)
#
# so the poster file, printed at 1.33x in the paper, puts a 17 pt label on the
# page at 23 pt against 10 pt body text. Each target therefore gets its own
# canvas and its own type sizes, chosen so the figure reads at roughly the size
# of the text around it, and the aspect differs too: the paper wants a wide,
# short figure spanning both columns, the poster a near-square one in a column.
TARGETS = [
    dict(
        name="poster",
        out=os.path.join(GIT, "IEEETransactions", "poster-cisuc", "images",
                         "efficiency_vs_cap_poster.pdf"),
        printed_mm=116.8, w=5.4, h=4.85, ncol=2,
        pt=dict(base=15, tick=16, axis=17, curve=17, legend=15),
        adjust=dict(left=0.215, right=0.965, top=0.97, bottom=0.435),
        lw=2.6, ms=8, star=420,
    ),
    dict(
        # One column of a two-column IEEE page, 252 pt = 88.9 mm, so the near
        # square shape the poster uses fits without spanning the text width.
        # Same canvas and aspect as the poster, smaller type: at a scale of
        # 0.65 a 14 pt label prints at 9.1 pt, just under the 10 pt body.
        name="paper",
        out=os.path.join(GIT, "paper1-iotj", "fig", "efficiency_vs_cap.pdf"),
        printed_mm=88.9, w=5.4, h=4.85, ncol=2,
        pt=dict(base=12, tick=13, axis=14, curve=14, legend=12),
        # Same strip as the cap-adherence figure, so the two sit on facing
        # columns with the legend at the same distance from the axis.
        adjust=dict(left=0.205, right=0.965, top=0.97, bottom=0.32),
        lw=1.6, ms=6.2, star=200,
    ),
]

BASE_RC = {
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
    "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
    "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
    "font.family": "serif",
}


def render(tj, t):
    """Draw the figure once, for one target."""
    PT = t["pt"]
    plt.rcParams.update(dict(BASE_RC, **{"font.size": PT["base"]}))
    fig, ax = plt.subplots(figsize=(t["w"], t["h"]))

    # The 62.5-75% band, shaded once behind everything.
    ax.axvspan(CONDITION_MHZ["75"], CONDITION_MHZ["62_5"],
               color=POSTER_SLATE, alpha=0.10, zorder=1)
    ax.axhline(100, color=BASELINE, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)

    xs = [CONDITION_MHZ[c] for c in ORDER]
    handles, drawn = [], []
    for model_key, style in MODEL_STYLE.items():
        base = tj[(model_key, "R1")]
        ys = [100.0 * tj[(model_key, c)] / base for c in ORDER]
        peak_i = ys.index(max(ys))
        line, = ax.plot(xs, ys, color=style["color"], linewidth=t["lw"],
                        marker="o", markersize=t["ms"], zorder=3,
                        label=style["label"], solid_capstyle="round")
        ax.scatter([xs[peak_i]], [ys[peak_i]], marker="*", s=t["star"],
                   color=CRITICAL_RED, edgecolor="white", linewidth=0.8, zorder=5)
        handles.append(line)
        drawn.append(ys)

    ax.set_xticks(xs)
    ax.set_xticklabels([CONDITION_LABEL[c].replace("\n", " ")
                                          .replace("R1 (turbo)", "turbo")
                                          .replace("%", "")
                        for c in ORDER], fontsize=PT["tick"])
    ax.tick_params(axis="y", labelsize=PT["tick"])
    ax.set_xlabel("Sustained clock, % of rated speed", fontsize=PT["axis"],
                  labelpad=6)
    ax.set_ylabel("Tokens per joule\n(uncapped $=100$)", fontsize=PT["axis"],
                  labelpad=5)
    ax.grid(True, axis="y", linewidth=0.6, alpha=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    span = xs[-1] - xs[0]
    # The last tick is a word, not a number, so it needs more room than the
    # others or it runs off the canvas.
    ax.set_xlim(xs[0] - 0.05 * span, xs[-1] + 0.09 * span)
    # The curves live between 100 and 174. Padding the axis down to 92 spent a
    # tenth of the height on nothing and pressed the four curves together; with
    # the legend out of the plot there is no reason to keep that room, so the
    # axis is cut to the data and the same curves are drawn further apart.
    ax.set_ylim(min(min(v) for v in drawn) - 3, max(max(v) for v in drawn) + 4)

    # The legend was in the lower-left corner of the plot, which cost the curves
    # the room they needed to separate. Below the axis it costs only canvas,
    # which is cheaper. It goes on the FIGURE, not the axes: hung off the axes
    # it was wider than they were, and bbox_inches="tight" then grew the canvas
    # sideways, which silently shrinks everything once the result is scaled to
    # a fixed width.
    handles += [
        plt.Line2D([0], [0], color="none", marker="*",
                   markersize=PT["legend"] + 2, markerfacecolor=CRITICAL_RED,
                   markeredgecolor="white", label="best efficiency"),
        plt.Rectangle((0, 0), 1, 1, color=POSTER_SLATE, alpha=0.18,
                      label="62.5\u201375\u2009% band"),
    ]
    fig.subplots_adjust(**t["adjust"])
    leg = fig.legend(handles=handles, loc="lower center", frameon=False,
                     ncol=t["ncol"], fontsize=PT["legend"], handletextpad=0.5,
                     columnspacing=1.6, labelspacing=0.4, borderaxespad=0.4)

    # The axis label and the legend are placed by different mechanisms, so
    # nothing stops them colliding and the first attempt did. Measure the gap
    # rather than trust the arithmetic.
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    gap_in = (ax.xaxis.label.get_window_extent(renderer=r).y0
              - leg.get_window_extent(renderer=r).y1) / fig.dpi
    scale = (t["printed_mm"] / 25.4) / t["w"]
    if gap_in <= 0:
        raise RuntimeError(f"{t['name']}: x label and legend overlap")

    # No tight_layout and no bbox_inches: the canvas must stay exactly w x h,
    # because the type sizes were chosen against the width it is printed at.
    os.makedirs(os.path.dirname(t["out"]), exist_ok=True)
    fig.savefig(t["out"], facecolor="white")
    plt.close(fig)
    print(f"  {t['name']:<7} {t['printed_mm']:.1f} mm wide, canvas {t['w']}x{t['h']} in "
          f"-> scale {scale:.2f}, {PT['axis']} pt label prints at "
          f"{PT['axis']*scale:.1f} pt, label/legend gap {gap_in*25.4*scale:.1f} mm")
    print(f"          {t['out']}")


def main():
    df = pd.read_csv(COMBINED_CSV,
                     usecols=["model_key", "condition", "tokens_per_joule"],
                     low_memory=False)
    tj = df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()

    for model_key, style in MODEL_STYLE.items():
        base = tj[(model_key, "R1")]
        ys = [100.0 * tj[(model_key, c)] / base for c in ORDER]
        i = ys.index(max(ys))
        print(f"  {style['label']:<18} peak {max(ys):6.1f}% at "
              f"{CONDITION_LABEL[ORDER[i]].replace(chr(10), ' ')}")
    print()

    for t in TARGETS:
        if not os.path.isdir(os.path.dirname(os.path.dirname(t["out"]))):
            print(f"  {t['name']:<7} skipped: no such repository")
            continue
        render(tj, t)


if __name__ == "__main__":
    main()
