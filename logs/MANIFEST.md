# Campaign manifest

Thirteen 48-hour campaigns were executed. **Seven feed the results reported in
the paper**; the other six are retained here for transparency but are
deliberately excluded from every table and figure. This file records which is
which, and why.

The selection is enforced in code, not by convention:

- `analysis_output/generate_results.py` → `EXCLUDED_CAMPAIGNS` (builds `combined_dataset.csv`)
- `analysis_output/generate_paper_numbers.py` → `REPORTED_CAMPAIGNS` (emits the paper's numbers)
- `analysis_output/generate_threats_figure.py` → `VALID_DIRS` (hardcoded campaign paths)

All three must stay in step, together with the table below. Changing one without
the others will silently skew the reported totals.

## Reported (7 campaigns, 24 runs, 1152 h)

| Campaign | Condition | Models | Freq. telemetry |
|---|---|---|---|
| `2026-05-01_48h_R1_no_throtting` | R1 unthrottled | Llama, DeepSeek | no |
| `2026-05-05_48h_R1_no_throtting` | R1 unthrottled | Qwen, Phi-3 | no |
| `2026-08-29_48h_100_throttling` | 100 % (3500 MHz) | all four | **yes** |
| `2026-06-14_48h_75_throttling` | 75 % (2625 MHz) | all four | no |
| `2026-07-02_48h_62_5_throttling` | 62.5 % (2188 MHz) | all four | no |
| `2026-07-19_48h_50_throttling` | 50 % (1750 MHz) | all four | **yes** |
| `2026-08-18_48h_87_5_throttling` | 87.5 % (3063 MHz) | all four | **yes** |

R1 is split across two sittings because the node runs one model at a time;
cross-model comparisons within R1 are therefore confounded with ambient drift
and are avoided in the paper.

`2026-05-09_48h_R2_no_throtting` and `2026-09-07_48h_R3_no_throtting` are the
unthrottled replicates. Neither is one of the 24 reported runs, but their power
samples are included in the reported sample total and they underpin the
reproducibility analysis.

The 100 % condition caps the clock at the 3500 MHz base frequency, which
disables turbo without constraining the core below its nominal rating. It is
the only condition sharing both kernel (6.8.0-138) and Ollama version (0.17.7)
with an unthrottled campaign (R3), so the R3-vs-100 % contrast isolates the cost
of turbo from the software-stack drift that separates R1/R2 from the later runs.

R3 carries three caveats that R1 and R2 do not, and they must travel with any
number derived from it: its DeepSeek run executed five days after the other
three and in a different room, following a power interruption; the ambient
logger covered only 24 % of its window, with a 42.8 h hole inside the DeepSeek
run; and all four models ran 4.7--5.0 °C hotter than in R1/R2, a uniform offset
consistent with room ambient rather than with anything in the node.

## Excluded: silently mis-throttled (2 campaigns)

Both were nominally capped but never ran under an effective cap. Neither left
any trace in its own telemetry, because both predate continuous frequency
logging. Each is superseded by a verified re-execution.

| Campaign | Nominal | What went wrong | Superseded by |
|---|---|---|---|
| `2026-07-11_48h_50_throttling` | 50 % | Sustained ≈2.4 GHz against a 1750 MHz cap. Detected post hoc from prefill throughput. | `2026-07-19` |
| `2026-05-20_48h_87_5_throttling` | 87.5 % | Prefill at ≈0.95 of unthrottled, off the ladder traced by the verified caps (0.87 / 0.80 / 0.70). Drew 38–42 % more power and ran 4–9 °C hotter than its replacement. Detected only once a verified re-execution existed. | `2026-08-18` |

`scaling_max_freq` does not survive a reboot, and the original orchestration
applied the cap once at campaign start. A single reboot or governor change was
enough to void a condition invisibly. The hardened protocol re-applies and
verifies the cap before every run and logs per-core frequency at 1 Hz.

## Excluded: valid replications (2 campaigns)

Valid runs that duplicate a condition already represented by its original
campaign. Merging them would collapse two independent runs under one condition
label. They are analysed separately, as replications, by
`compare_62_5_campaigns.py` and `compare_75_campaigns.py`.

| Campaign | Replicates | Freq. telemetry |
|---|---|---|
| `2026-07-27_48h_62_5_throttling` | `2026-07-02` (62.5 %) | yes |
| `2026-08-08_48h_75_throttling` | `2026-06-14` (75 %) | yes |

## Known data gaps

- `2026-07-19` (50 %), Phi-3 Mini: the power logger stopped after a network
  timeout to the smart plug and did not recover, leaving 40.1 h of the 48 h
  covered. 17.6 % of that run's fused records carry no power sample; they are
  dropped rather than imputed. Quantified in the paper's Threats section.
- No ambient temperature sensor was deployed during any campaign. Outdoor
  temperature is reconstructed from ERA5 reanalysis; see
  `analysis_output/ambient_correlation.py`.
