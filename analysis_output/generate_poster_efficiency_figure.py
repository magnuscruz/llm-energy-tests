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

# The tikzposter draft is gone and the CISUC poster now keeps its own assets,
# so the figure is written straight into them.
POSTER_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "IEEETransactions",
    "poster-cisuc", "images"))

# The poster's own palette, so the figure does not arrive from a different
# document. ink/slate/accent are the three colours main.tex defines.
POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"
POSTER_ACCENT = "#C2552E"

# Sized for where it is printed, not for the screen. The poster gives it a
# column of 116.8 mm (A2 text width 369.5 mm, three columns, 9.5 mm gutters),
# which is 4.6 in, so a figure 5.4 in wide is scaled by 0.85 on the page and a
# 17 pt label lands at about 14.5 pt. The body text around it is 21.5 pt. Making
# the figure canvas smaller is what buys that: the same labels on a 9 in canvas
# would print at 7.7 pt, which is the size they were before this was measured.
FIG_W, FIG_H = 5.4, 4.6
PT = dict(base=15, tick=16, axis=17, curve=17, legend=15)

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": BASELINE, "axes.labelcolor": POSTER_INK,
    "text.color": POSTER_INK, "xtick.color": POSTER_SLATE,
    "ytick.color": POSTER_SLATE, "grid.color": "#e1e0d9",
    "font.family": "serif", "font.size": PT["base"],
})


def main():
    df = pd.read_csv(COMBINED_CSV,
                     usecols=["model_key", "condition", "tokens_per_joule"],
                     low_memory=False)
    tj = df.groupby(["model_key", "condition"])["tokens_per_joule"].mean()

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

    # The 62.5-75% band, shaded once behind everything.
    ax.axvspan(CONDITION_MHZ["75"], CONDITION_MHZ["62_5"],
               color=POSTER_SLATE, alpha=0.10, zorder=1)
    ax.axhline(100, color=BASELINE, linewidth=1.2, linestyle=(0, (4, 3)), zorder=2)

    xs = [CONDITION_MHZ[c] for c in ORDER]
    handles, drawn = [], []
    for model_key, style in MODEL_STYLE.items():
        base = tj[(model_key, "R1")]
        ys = [100.0 * tj[(model_key, c)] / base for c in ORDER]
        peak_i = ys.index(max(ys))
        line, = ax.plot(xs, ys, color=style["color"], linewidth=2.6,
                        marker="o", markersize=8, zorder=3,
                        label=style["label"], solid_capstyle="round")
        ax.scatter([xs[peak_i]], [ys[peak_i]], marker="*", s=420,
                   color=CRITICAL_RED, edgecolor="white", linewidth=1.0, zorder=5)
        handles.append(line)
        drawn.append(ys)
        print(f"  {style['label']:<18} peak {max(ys):6.1f}% at "
              f"{CONDITION_LABEL[ORDER[peak_i]].replace(chr(10), ' ')}")

    ax.set_xticks(xs)
    ax.set_xticklabels([CONDITION_LABEL[c].replace("\n", " ")
                                          .replace("R1 (turbo)", "turbo")
                                          .replace("%", "")
                        for c in ORDER], fontsize=PT["tick"])
    ax.tick_params(axis="y", labelsize=PT["tick"])
    ax.set_xlabel("Sustained clock, % of rated speed", fontsize=PT["axis"],
                  labelpad=8)
    ax.set_ylabel("Tokens per joule\n(uncapped $=100$)", fontsize=PT["axis"],
                  labelpad=6)
    ax.grid(True, axis="y", linewidth=0.8, alpha=0.7)
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
    lo = min(min(v) for v in drawn) - 3
    hi = max(max(v) for v in drawn) + 4
    ax.set_ylim(lo, hi)

    # The legend was in the lower-left corner of the plot, which cost the curves
    # the room they needed to separate. Below the axis it costs only canvas,
    # which is cheaper.
    handles += [
        plt.Line2D([0], [0], color="none", marker="*", markersize=17,
                   markerfacecolor=CRITICAL_RED, markeredgecolor="white",
                   label="best efficiency"),
        plt.Rectangle((0, 0), 1, 1, color=POSTER_SLATE, alpha=0.18,
                      label="62.5\u201375\u2009% band"),
    ]
    # On the FIGURE, not on the axes, and the strip for it is reserved with
    # subplots_adjust. Hung off the axes instead, it was wider than they were,
    # and bbox_inches="tight" then grew the canvas sideways -- which silently
    # shrinks everything once the result is scaled to a fixed column width.
    # Two columns, not three: three made the legend wider than the canvas and
    # it was clipped at both ends. The left margin holds a two-line y label at
    # 17 pt, which 0.165 did not.
    fig.subplots_adjust(left=0.215, right=0.965, top=0.97, bottom=0.355)
    fig.legend(handles=handles, loc="lower center", frameon=False, ncol=2,
               fontsize=PT["legend"], handletextpad=0.5, columnspacing=1.6,
               labelspacing=0.55, borderaxespad=0.5)

    # No tight_layout and no bbox_inches: the canvas must stay exactly
    # FIG_W x FIG_H, because every type size here was chosen against the
    # 116.8 mm column it is printed in.
    out = os.path.join(POSTER_DIR, "efficiency_vs_cap_poster.pdf")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
