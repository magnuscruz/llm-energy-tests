# llm-energy-tests — Agent Rules & Local Context (Loaded from Claude)

Sustained-inference energy and reliability measurements for LLMs on a CPU-only edge node: campaign orchestration, telemetry, and the analysis pipeline behind the published results.

## Mandatory Reading

- **`logs/MANIFEST.md`**: Eleven 48-hour campaigns were run; six feed the reported results. The manifest says which is which and why. Two campaigns silently ran without an effective frequency cap and are superseded by verified re-executions; two others are valid replications that duplicate a condition. **Analysing the wrong subset is the easiest mistake to make with this data.**

## Ground Rules for Analysis

1. **Recompute from the raw CSVs**: `logs/*/deep_aging/*_merged_analysis.csv` is one row per inference event.
2. **Never count events from `combined_dataset.csv`**: It carries a 60-sample moving average and drops rows whose power sample is missing, so it both smooths magnitudes and undercounts. Use it for figures, not for totals.
3. **Cover every campaign, not a subset**: Patterns that look clean across four campaigns have dissolved when all ten were included.
4. **Filenames encode the target, not the achievement**: Every file is named `*_48.00h_*` regardless of what completed. One run carries 40.1 h of power telemetry, not 48; check spans before trusting a campaign.
5. **Two selection lists must stay in step**: `EXCLUDED_CAMPAIGNS` in `analysis_output/generate_results.py` and `REPORTED_CAMPAIGNS` in `analysis_output/generate_paper_numbers.py`. `generate_threats_figure.py` hardcodes campaign paths as well. Desynchronising them once put a reported total 63% above the sum of the corresponding table.

## Environment

- `.venv` carries `pandas`, `numpy`, and `matplotlib`. `scipy` is optional.
- Python executable: `/home/magnus/git/llm-energy-tests/.venv/bin/python`
