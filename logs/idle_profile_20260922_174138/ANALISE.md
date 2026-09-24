# Residency power profile, Llama 3.1 8B — 2026-09-22

Companion to `logs/idle_profile_20260922_080201`, which measured the same four
states with `qwen2.5:0.5b`. That run left one question open: Qwen holds 0.7 GB of
weights, and DRAM refresh might not stay free at Llama 3.1 8B's 5.5 GB. This
answers it.

Same script, same meter, same units (`scripts/profile_idle_power.sh`, Tapo P115,
`get_current_power`, 1 Hz). Governor `powersave`, no cap, kernel 6.8.0-138,
Ollama 0.17.7. Phases held 150 s, first 25 s of each discarded as settling.

| Phase | n | mean | median | p05 | p95 |
|---|---|---|---|---|---|
| `idle_nomodel` — engine up, no weights | 158 | 32.2 W | 30.0 | 30.0 | 33.0 |
| `idle_model` — 5.5 GB resident, no requests | 124 | 30.1 W | 30.0 | 30.0 | 31.0 |
| `busy` — closed-loop generation | 167 | 149.4 W | 149.0 | 146.0 | 153.0 |
| `idle_model_after` — resident idle, post-load | 124 | 30.1 W | 30.0 | 30.0 | 31.0 |

## What it settles

**Model size does not change the cost of residency.** Holding 5.5 GB resident
draws 30.0 W at the median, identical to holding 0.7 GB and identical to holding
nothing. The apparent −2.1 W is the same artifact as in the Qwen run: the
`idle_nomodel` mean sits above its own median because that phase catches
background work, while the medians agree exactly. Eight times the resident
footprint costs nothing measurable at the wall.

That closes the open question from the Qwen profile. An orchestrator has no
energy reason to evict weights between requests at any of the model sizes
studied here, which removes a whole class of policy from consideration.

**The measurement chain cross-validates again.** 149.4 W saturated here against
151.9 W for Llama 3.1 8B in the R3 campaign, 1.7 % apart across separate runs on
the same instrumentation. The Qwen pair agreed to 1.9 %.

**No hysteresis, at this size either.** Idle after load returns to 30.1 W,
identical to idle before it.

## Still not measured

- Idle under the `performance` governor rather than `powersave`. Changing it
  needs `sudo`, which the non-interactive path does not have.
- True suspend. The 30 W floor is with the system awake throughout, and that
  remains the only regime where a race-to-sleep argument could be recovered.
