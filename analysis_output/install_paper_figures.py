#!/usr/bin/env python3
"""Copy generated figures into the manuscript under the names it expects.

The mapping between what generate_results.py writes and what the .tex includes
was tacit: the files were renamed by hand, so nothing recorded which generated
figure belonged under which caption. Putting the wrong figure under a caption
is worse than any legibility problem, so the mapping lives here, is checked,
and fails loudly if a source is missing.

Run generate_results.py first, then this.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_FIG = os.path.abspath(os.path.join(HERE, "..", "..", "IEEETransactions",
                                         "results", "fig"))

# generated name (no extension) -> name the manuscript includes
MAPPING = {
    "pair_qwen_phi3_01_cpu_temp":              "thermal_qwen_phi3",
    "pair_llama_deepseek_01_cpu_temp":         "thermal_llama_deepseek",
    "pair_qwen_phi3_02_ram_used_mb":           "ram_qwen_phi3",
    "pair_llama_deepseek_02_ram_used_mb":      "ram_llama_deepseek",
    "pair_qwen_phi3_00_reproducibility_R1_R2": "repro_qwen_phi3",
    "pair_llama_deepseek_00_reproducibility_R1_R2": "repro_llama_deepseek",
    "pair_qwen_phi3_03_decode_tps":            "decode_tps_timeseries_qwen_phi3",
    "bar_01_decode_tps":                       "decode_tps",
    "bar_02_power":                            "power_consumption",
    "bar_03_efficiency":                       "tokens_joule_efficiency",
    "efficiency_vs_cap":                       "efficiency_vs_cap",
}


def main():
    missing = [s for s in MAPPING if not os.path.exists(os.path.join(HERE, s + ".pdf"))]
    if missing:
        sys.exit("missing generated figures (run generate_results.py first):\n  "
                 + "\n  ".join(missing))
    if not os.path.isdir(PAPER_FIG):
        sys.exit(f"manuscript figure directory not found: {PAPER_FIG}")
    for src, dst in sorted(MAPPING.items()):
        shutil.copy2(os.path.join(HERE, src + ".pdf"),
                     os.path.join(PAPER_FIG, dst + ".pdf"))
        print(f"  {src}.pdf -> {dst}.pdf")
    print(f"{len(MAPPING)} figures installed into {PAPER_FIG}")


if __name__ == "__main__":
    main()
