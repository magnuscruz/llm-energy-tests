# Orchestration logs

Standard output from `scripts/run_benchmark_pair.sh` during two campaign runs,
kept because of what the `[Verify]` lines carry: the frequency cap, governor and
energy-performance preference as read back from `sysfs` at run time, rather than
as the configuration intended them.

That matters here more than it would elsewhere. Two campaigns in this project
silently executed without an effective cap, and `run_config.log` records what was
applied at each model's start, not what held afterwards. These logs corroborate
the configuration independently.

- `benchmark_run_pair.log` — a full four-model campaign.
- `benchmark_deepseek_restart.log` — the DeepSeek re-run of campaign R3, after
  the laboratory move and the power interruption. It records the model override
  and that it wrote into an existing campaign directory, which is the history
  `MANIFEST.md` describes in prose.

Both were scanned for credentials before being committed. They are stdout, so
they carry whatever the script printed and nothing else.
