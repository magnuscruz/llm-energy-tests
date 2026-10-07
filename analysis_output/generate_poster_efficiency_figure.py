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

POSTER_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "IEEETransactions", "poster"))

# The poster's own palette, so the figure does not arrive from a different
# document. ink/slate/accent are the three colours main.tex defines.
POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"
POSTER_ACCENT = "#C2552E"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
    "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
    "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
    "font.family": "serif", "font.size": 13,
})


def main():
    df = pd.read_csv(COMBINED_CSV,
                     usecols=["model_key", "condition", "tokens_per_joule"],
                     low_memory=False)
    tj = df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()

    fig, ax = plt.subplots(figsize=(9.0, 5.1))

    # The 62.5-75% band, shaded once behind everything.
    ax.axvspan(CONDITION_MHZ["75"], CONDITION_MHZ["62_5"],
               color=POSTER_SLATE, alpha=0.10, zorder=1)
    ax.axhline(100, color=BASELINE, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)

    xs = [CONDITION_MHZ[c] for c in ORDER]
    curves = []
    for model_key, style in MODEL_STYLE.items():
        base = tj[(model_key, "R1")]
        ys = [100.0 * tj[(model_key, c)] / base for c in ORDER]
        peak_i = ys.index(max(ys))
        ax.plot(xs, ys, color=style["color"], linewidth=3.0,
                marker="o", markersize=9, zorder=3, label=style["label"],
                solid_capstyle="round")
        ax.scatter([xs[peak_i]], [ys[peak_i]], marker="*", s=600,
                   color=CRITICAL_RED, edgecolor="white", linewidth=1.2, zorder=5)
        curves.append((ys[0], style))
        print(f"  {style['label']:<18} peak {max(ys):6.1f}% at "
              f"{CONDITION_LABEL[ORDER[peak_i]].replace(chr(10), ' ')}")

    # Name each curve at its left end, so the eye does not shuttle to a key. Two
    # of the four start within a few points of each other, and on a flattened
    # axis their labels overlap, so the labels are pushed apart vertically while
    # the leader dots stay on the curves. The nudge is in display points and
    # never reorders them, so the labels still read top-to-bottom as the curves
    # do at that edge.
    curves.sort(key=lambda t: t[0])
    min_gap = 0.06 * (ax.get_ylim()[1] - ax.get_ylim()[0])
    placed, prev = [], None
    for y0, style in curves:
        y = y0 if prev is None else max(y0, prev + min_gap)
        placed.append((y, y0, style))
        prev = y

    span = xs[-1] - xs[0]
    label_x = xs[0] - 0.025 * span
    for y, y0, style in placed:
        # A leader only where the label had to leave its curve; drawing one for
        # every label would add three lines that say nothing.
        if abs(y - y0) > 0.4:
            ax.plot([label_x, xs[0]], [y, y0], color=style["color"],
                    linewidth=1.2, alpha=0.55, zorder=2, clip_on=False)
        ax.annotate(style["label"], xy=(label_x, y), ha="right", va="center",
                    fontsize=14, color=style["color"], fontweight="bold",
                    annotation_clip=False)

    ax.set_xticks(xs)
    ax.set_xticklabels([CONDITION_LABEL[c].replace("\n", " ") for c in ORDER],
                       fontsize=14)
    ax.set_xlabel("Sustained clock, as a share of rated speed", fontsize=15,
                  labelpad=10)
    ax.set_ylabel("Tokens per joule\n(uncapped $=100$)", fontsize=15, labelpad=10)
    ax.grid(True, axis="y", linewidth=0.8, alpha=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Headroom on the left for the curve labels, which sit outside the data.
    ax.set_xlim(xs[0] - 0.34 * span, xs[-1] + 0.04 * span)

    star = plt.Line2D([0], [0], color="none", marker="*", markersize=20,
                      markerfacecolor=CRITICAL_RED, markeredgecolor="white",
                      label="best efficiency")
    band = plt.Rectangle((0, 0), 1, 1, color=POSTER_SLATE, alpha=0.18,
                         label="62.5–75 % band")
    ax.legend(handles=[star, band], loc="lower left", frameon=False,
              fontsize=13, handletextpad=0.6, borderaxespad=0.8)

    fig.tight_layout()
    out = os.path.join(POSTER_DIR, "efficiency_vs_cap_poster.pdf")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
