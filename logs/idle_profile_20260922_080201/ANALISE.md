# Idle and residency power profile — 2026-09-22

Wall-plug power for the node doing nothing, holding a model, and working, on the
same meter, cadence and units as the campaigns (`tapo` P115, `get_current_power`,
1 Hz). Produced by `scripts/profile_idle_power.sh`.

Conditions: governor `powersave`, EPP `balance_performance`, `scaling_max_freq`
4800000 (no cap), kernel 6.8.0-138, Ollama 0.17.7, model `qwen2.5:0.5b`.
Each phase held 240 s; the first 25 s of each are discarded as settling.

| Phase | n | mean | median | p05 | p95 |
|---|---|---|---|---|---|
| `idle_nomodel` — engine up, no weights | 240 | 32.2 W | 30.0 | 30.0 | 52.0 |
| `idle_model` — weights resident, no requests | 209 | 30.5 W | 30.0 | 30.0 | 32.0 |
| `busy` — closed-loop generation | 213 | 132.1 W | 133.0 | 125.0 | 136.0 |
| `idle_model_after` — resident idle, post-load | 208 | 30.5 W | 30.0 | 30.0 | 31.0 |

`idle_nomodel`'s mean and p95 are inflated: that window overlapped a `git gc`
and a 100 MB `git bundle create` run on the node. Its median and p05 agree with
the clean `idle_model` phase, so the floor is 30 W and the mean is the artifact.

## What it establishes

**The platform floor is 30 W**, against 132 W saturated — 23 % of the load-time
draw is paid per second whether or not there is work.

**Holding a model resident is free.** 30.5 W with `qwen2.5:0.5b` in memory
against a 30.0 W median without it. An orchestrator has no energy reason to
evict weights between requests. This was measured again for Llama 3.1 8B, which
holds 5.5 GB against Qwen's 0.7 GB, in case DRAM refresh stopped being free at
that size: it does not. See `logs/idle_profile_20260922_174138`.

**There is no hysteresis.** Idle after load returns to 30.5 W, identical to idle
before it, so the states can be treated as memoryless by a controller.

**The measurement chain cross-validates.** 132.1 W saturated here against
134.6 W for the same model in the R3 campaign — 1.9 % apart, separate runs,
same instrumentation.

## Consequence for the orchestration policy

With fixed work `W` and a fixed deadline `T`, total energy is
`W·(P_busy − P_floor)/tps + P_floor·T`. The second term is constant under any
policy, so only **dynamic** power per token separates them. Capping still wins,
and by more than the total-power figure suggests: from unthrottled to the 100 %
cap, dynamic power falls 31.5 % against 24.5 % of total, for 4.6 % of throughput.

Race-to-sleep does not apply on this platform. Finishing early only pays if idle
is cheap, and idle here costs 23 % of busy — there is no deep enough sleep state
to race toward. The 62.5–75 % optimum reported in paper 1 therefore survives
intermittent arrival, not only saturation. That was not the expected result: the
floor was measured because it looked capable of overturning the recommendation.

## Not yet measured

- Idle under `performance` vs `powersave` governor; changing it needs `sudo`.
- True suspend. The 30 W floor is with the system awake throughout, which is the
  only regime where a race-to-sleep argument could still be recovered.
