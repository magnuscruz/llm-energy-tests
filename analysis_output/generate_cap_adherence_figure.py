#!/usr/bin/env python3
"""Single-panel cap-adherence figure, sized for the column it is printed in.

WHAT IT SHOWS. Prefill is compute-bound, so its throughput tracks clock rate.
Fitting that relation on campaigns whose frequency was verified gives an
expected value at any cap. The original 50% campaign (with turbo / unmanaged)
sits far above its expectation, showing how a run that silently lost its cap
was detected. The verified 50% campaign (without turbo / capped) aligns closely
with the expected compute-bound scaling ladder across all four models.

This figure demonstrates the problem of not managing turbo under throttling:
cores boost ~750-800 MHz above the nominal 1750 MHz cap (+21% to +31% prefill
throughput), silently defeating the frequency cap.

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
    CRITICAL_RED, BASELINE, prefill_mean, LOGS_DIR,
)

GIT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VERIFIED_50_DIR = os.path.join(LOGS_DIR, "2026-07-19_48h_50_throttling", "deep_aging")

POSTER_INK = "#1B2A3A"
POSTER_SLATE = "#41566B"

TARGET = dict(
    name="paper",
    out=os.path.join(GIT, "paper1-iotj", "fig", "cap_adherence.pdf"),
    printed_mm=88.9, w=5.4, h=4.8, ncol=2,
    pt=dict(base=11, tick=11.5, axis=12.5, legend=9.5),
    adjust=dict(left=0.185, right=0.965, top=0.97, bottom=0.33),
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

    # Shaded band highlighting effective turbo operating frequency (≈2.47 to 2.55 GHz)
    ax.axvspan(2470, 2560, color="#d03b3b", alpha=0.08, zorder=1)
    ax.text(2515, 0.94, "Implied turbo band\n(≈2.5 GHz)",
            color="#a82222", fontsize=7.5, ha="center", va="top", style="italic", fontweight="semibold")

    xs = np.array([mhz for _, mhz in VALID_DIRS.values()], dtype=float)
    handles = []
    data_summary = {}

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
        implied_mhz = (observed_inv - intercept) / slope

        data_summary[model_key] = {
            "style": style,
            "expected": expected,
            "ver": observed_ver,
            "inv": observed_inv,
            "implied_mhz": implied_mhz,
        }

        # Small dodge on 50% markers to make both clear and prevent overlap
        x_ver = 1720
        x_inv = 1780

        # Expected at 50% (extrapolated) - hollow circle
        ax.scatter([NOMINAL_50_MHZ], [expected], marker="o", s=34,
                   facecolor="white", edgecolor=style["color"],
                   linewidth=1.2, zorder=4)

        # Verified 50% (without turbo) - solid circle
        ax.scatter([x_ver], [observed_ver], marker="o", s=30,
                   color=style["color"], edgecolor="white", linewidth=0.6, zorder=5)

        # Original 50% (with turbo unmanaged) - 'X' with model color and red outline
        ax.scatter([x_inv], [observed_inv], marker="X", s=56,
                   color=style["color"], edgecolor=CRITICAL_RED, linewidth=1.1, zorder=6)

        # Dotted connector between verified and with-turbo
        ax.plot([x_ver, x_inv], [observed_ver, observed_inv],
                color=style["color"], linestyle=":", linewidth=0.9, alpha=0.5, zorder=3)

        # Horizontal dashed projection to implied MHz on linear fit
        ax.plot([x_inv, implied_mhz], [observed_inv, observed_inv],
                color=style["color"], linestyle="--", linewidth=0.8, alpha=0.55, zorder=2)
        ax.scatter([implied_mhz], [observed_inv], marker="|", color=style["color"], s=32, zorder=3)

        handles.append(line)
        print(f"  {style['label']:<18} expected {expected:.3f}  ver(no-turbo) {observed_ver:.3f}"
              f"  orig(turbo) {observed_inv:.3f}  implied(orig) {implied_mhz:.0f} MHz")

    # Inset summary table in the empty bottom-right region
    table_text = (
        r"$\bf{50\%\ Cap\ Values\ (1750\ MHz):}$" + "\n"
        r"$\bf{Model}$        $\bf{No\ Turb}$  $\bf{w/\ Turb}$   $\bf{Implied}$" + "\n"
        f"Llama 3.1:     {data_summary['llama3.1_8b']['ver']:.3f}    {data_summary['llama3.1_8b']['inv']:.3f}   {data_summary['llama3.1_8b']['implied_mhz']:.0f} MHz\n"
        f"Phi-3 Mini:    {data_summary['phi3_mini']['ver']:.3f}    {data_summary['phi3_mini']['inv']:.3f}   {data_summary['phi3_mini']['implied_mhz']:.0f} MHz\n"
        f"DeepSeek-v2:   {data_summary['deepseek-v2_lite']['ver']:.3f}    {data_summary['deepseek-v2_lite']['inv']:.3f}   {data_summary['deepseek-v2_lite']['implied_mhz']:.0f} MHz\n"
        f"Qwen2.5:       {data_summary['qwen2.5_0.5b']['ver']:.3f}    {data_summary['qwen2.5_0.5b']['inv']:.3f}   {data_summary['qwen2.5_0.5b']['implied_mhz']:.0f} MHz\n"
        r"$\it{Unmanaged\ turbo\ overshoot:\ +21\%\ to\ +31\%}$"
    )
    ax.text(3550, 0.515, table_text,
            fontsize=7.3, fontfamily="monospace", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdfdfd", edgecolor="#d5d4cd", alpha=0.96))

    ax.set_xticks([NOMINAL_50_MHZ] + list(xs))
    ax.set_xticklabels(["1750"] + [f"{int(v)}" for v in xs], fontsize=PT["tick"])
    ax.tick_params(axis="y", labelsize=PT["tick"])
    ax.set_xlabel("Nominal frequency cap (MHz)", fontsize=PT["axis"], labelpad=6)
    ax.set_ylabel("Prefill throughput\n(fraction of uncapped)",
                  fontsize=PT["axis"], labelpad=5)
    ax.grid(True, axis="y", linewidth=0.6, alpha=0.7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlim(NOMINAL_50_MHZ - 130, xs.max() + 120)
    ax.set_ylim(0.50, 1.01)

    handles += [
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor="white",
                   markeredgecolor=POSTER_SLATE, markersize=PT["legend"] - 4,
                   label="expected at 50 %"),
        plt.Line2D([0], [0], marker="X", color="none",
                   markerfacecolor=POSTER_SLATE, markeredgecolor=CRITICAL_RED,
                   markersize=PT["legend"] - 2, label="50 % with turbo (unmanaged)"),
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor=POSTER_SLATE, markeredgecolor="white",
                   markersize=PT["legend"] - 4, label="50 % without turbo (verified)"),
    ]
    scale = (t["printed_mm"] / 25.4) / t["w"]
    fig.subplots_adjust(**t["adjust"])
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    xl_y0_fig = ax.xaxis.label.get_window_extent(renderer=r).y0 / fig.bbox.height
    desired_gap_mm = 2.0  # Tight, clean gap in print (2.0 mm)
    gap_fig = (desired_gap_mm / 25.4 / scale) / t["h"]

    leg = fig.legend(handles=handles, loc="upper center",
                     bbox_to_anchor=(0.58, xl_y0_fig - gap_fig), frameon=False,
                     ncol=t["ncol"], fontsize=PT["legend"], handletextpad=0.5,
                     columnspacing=1.2, labelspacing=0.35, borderaxespad=0.2)

    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    gap_in = (ax.xaxis.label.get_window_extent(renderer=r).y0
              - leg.get_window_extent(renderer=r).y1) / fig.dpi
    if gap_in <= 0:
        raise RuntimeError("x label and legend overlap")

    os.makedirs(os.path.dirname(t["out"]), exist_ok=True)
    fig.savefig(t["out"], facecolor="white", bbox_inches="tight")
    # Also save a png copy alongside
    png_out = os.path.splitext(t["out"])[0] + ".png"
    fig.savefig(png_out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"\n  {t['printed_mm']:.1f} mm wide, canvas {t['w']}x{t['h']} in -> "
          f"scale {scale:.2f}, {PT['axis']} pt label prints at "
          f"{PT['axis']*scale:.1f} pt, label/legend gap {gap_in*25.4*scale:.1f} mm")
    print(f"  {t['out']}")


if __name__ == "__main__":
    render(TARGET)
