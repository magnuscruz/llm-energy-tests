#!/bin/bash
# ==============================================================================
# Idle and residency power profile.
#
# Everything in the 48-hour campaigns was measured at 100% duty cycle, where
# race-to-sleep cannot apply: there is no idle time to finish early into. An
# orchestrator faces arrival gaps, so the decision it has to make -- cap low and
# run slow, or run fast and idle -- turns on numbers the campaigns never
# recorded: what the node costs per second doing nothing, and what it costs to
# hold a model resident between requests.
#
# This measures four states at the same wall-plug meter, cadence and units as
# the campaigns (tapo P115, get_current_power, 1 Hz), so the numbers compose
# with the existing dataset rather than sitting beside it.
#
#   idle_nomodel      engine up, nothing loaded      -> platform floor
#   idle_model        model resident, no requests    -> cost of residency
#   busy              closed-loop generation         -> sanity check vs campaigns
#   idle_model_after  back to resident idle          -> hysteresis after load
#
# C-state residency counters are sampled at every phase boundary. They are
# world-readable, so this needs no privilege; changing the governor does, and is
# deliberately left out (see PROFILE.md).
#
# Usage: ./scripts/profile_idle_power.sh [hold_seconds]   (default 240)
# ==============================================================================
set -u

HOLD=${1:-240}
MODEL=${MODEL:-qwen2.5:0.5b}
PROMPT="Analyze the implications of software aging on distributed edge network reliability."

cd "$(dirname "$0")/.." || exit 1
REPO=$(pwd)

[ -f .env ] || { echo "no .env at $REPO" >&2; exit 1; }
set -a; . ./.env; set +a
PY=$([ -x venv/bin/python3 ] && echo "$REPO/venv/bin/python3" || echo "$REPO/.venv/bin/python3")
[ -x "$PY" ] || { echo "no python venv" >&2; exit 1; }

OUT="$REPO/logs/idle_profile_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "writing to $OUT"

# Same reader as start_tapo_monitor() in run_benchmark_pair.sh: identical units
# and cadence, so these watts are directly comparable to *_physical.csv.
cat > "$OUT/tapo_idle_mon.py" <<'PYEOF'
import asyncio, os, sys, time
from tapo import ApiClient

async def monitor():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    print('timestamp,power_w')
    sys.stdout.flush()
    while True:
        energy = await device.get_current_power()
        print(f'{int(time.time())},{energy.current_power}')
        sys.stdout.flush()
        await asyncio.sleep(1)

asyncio.run(monitor())
PYEOF

"$PY" "$OUT/tapo_idle_mon.py" > "$OUT/power.csv" 2> "$OUT/power.err" &
MON=$!
cleanup() {
    kill "$MON" 2>/dev/null
    curl -s localhost:11434/api/generate \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"x\",\"stream\":false,\"keep_alive\":0}" >/dev/null 2>&1
}
trap cleanup EXIT

sleep 5
if [ ! -s "$OUT/power.csv" ]; then
    echo "plug not answering; see $OUT/power.err" >&2
    head -3 "$OUT/power.err" >&2
    exit 1
fi

echo "timestamp,phase" > "$OUT/phases.csv"
echo "phase,timestamp,state,time_us,usage" > "$OUT/cstates.csv"

sample_cstates() {
    local phase=$1 ts
    ts=$(date +%s)
    for s in /sys/devices/system/cpu/cpu0/cpuidle/state*/; do
        [ -r "$s/name" ] || continue
        echo "$phase,$ts,$(cat "$s/name"),$(cat "$s/time"),$(cat "$s/usage")" >> "$OUT/cstates.csv"
    done
}

mark() {
    echo "$(date +%s),$1" >> "$OUT/phases.csv"
    sample_cstates "$1"
    echo "  [$(date +%H:%M:%S)] $1"
}

# --- 1. platform floor: engine up, no weights resident -----------------------
curl -s localhost:11434/api/generate \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"x\",\"stream\":false,\"keep_alive\":0}" >/dev/null 2>&1
sleep 20
mark idle_nomodel
sleep "$HOLD"

# --- 2. cost of holding the model resident -----------------------------------
curl -s localhost:11434/api/generate \
    -d "{\"model\":\"$MODEL\",\"prompt\":\"hi\",\"stream\":false,\"keep_alive\":\"60m\"}" >/dev/null 2>&1
sleep 30
mark idle_model
sleep "$HOLD"

# --- 3. saturated, for comparison against the campaign dataset ---------------
mark busy
END=$(( $(date +%s) + HOLD ))
while [ "$(date +%s)" -lt "$END" ]; do
    curl -s localhost:11434/api/generate \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"$PROMPT\",\"stream\":false,\"keep_alive\":\"60m\"}" >/dev/null 2>&1
done

# --- 4. does idle return to where it was, or settle higher? ------------------
mark idle_model_after
sleep "$HOLD"

mark done
echo "done: $OUT"
