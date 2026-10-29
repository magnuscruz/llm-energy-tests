#!/bin/bash
# ==============================================================================
# Rejuvenation Cost & Calibration Profile (Paper 3 & Paper 4 / Agenda A2, A3, A4)
#
# Measures the wall-plug energy (Tapo P115 at 1 Hz), CPU temperature, ambient
# temperature & humidity (BLE ThermoPro), wall-clock latency, memory footprint
# (Runner RSS + OS page cache), runner PID continuity, and post-action
# throughput for each candidate rejuvenation action across the four edge LLMs:
#
#   1. runner_restart_warm  Terminates ollama runner subprocess (keep_alive=0),
#                           clearing all C++ allocator arenas & KV-cache while
#                           keeping GGUF weights in OS page cache.
#   2. page_cache_drop      Evicts GGUF blobs from OS page cache via
#                           POSIX_FADV_DONTNEED (or drop_caches=3 if root) while
#                           keeping the ollama runner process alive.
#   3. runner_restart_cold  Terminates ollama runner subprocess AND evicts OS
#                           page cache, forcing a full cold reload from NVMe SSD.
#   4. idle_pause_control   Pauses inference for the exact duration of
#                           runner_restart_warm without resetting any layer
#                           (Row 1 control of Paper 3 Table 1).
#
# Mandatory Pre-Flight Check (Agenda A4):
#   Verifies before starting that ALL THREE telemetry streams are live:
#     (a) Out-of-band wall-plug power (Tapo P115 -> power.csv)
#     (b) On-die CPU package/core temperature (lm-sensors -> system_metrics.csv)
#     (c) Ambient temperature & relative humidity (ambient_ble.csv / ThermoPro)
#
# Usage:
#   ./scripts/profile_rejuvenation_cost.sh [reps_per_action]
# ==============================================================================
set -u

REPS=${1:-5}
MODELS=("qwen2.5:0.5b" "phi3:mini" "llama3.1:8b" "deepseek-v2:lite")
PROMPT="Analyze the implications of software aging on distributed edge network reliability."

cd "$(dirname "$0")/.." || exit 1
REPO=$(pwd)

[ -f .env ] || { echo "[-] no .env at $REPO" >&2; exit 1; }
set -a; . ./.env; set +a
PY=$([ -x venv/bin/python3 ] && echo "$REPO/venv/bin/python3" || echo "$REPO/.venv/bin/python3")
[ -x "$PY" ] || { echo "[-] no python venv at $PY" >&2; exit 1; }

AMBIENT_SRC="${AMBIENT_LOG:-/home/ubuntu/ambient_ble.csv}"
[ ! -f "$AMBIENT_SRC" ] && [ -f "$HOME/ambient_ble.csv" ] && AMBIENT_SRC="$HOME/ambient_ble.csv"

OUT="$REPO/logs/rejuvenation_cost_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"
echo "[*] Writing rejuvenation cost profile to: $OUT"

# ==============================================================================
# PRE-FLIGHT CHECK 1: CPU TEMPERATURE SENSOR (lm-sensors)
# ==============================================================================
CPU_TEMP_INIT=$(sensors 2>/dev/null | awk '/Package id 0:|Core 0:/ {gsub(/[+°C]/,"",$0); for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.[0-9]+$/){print $i; exit}}')
if [ -z "$CPU_TEMP_INIT" ]; then
    echo "[-] PRE-FLIGHT FAILED: lm-sensors returned no CPU temperature reading." >&2
    exit 1
fi
echo "[+][Pre-Flight 1/3] CPU Temperature sensor OK: ${CPU_TEMP_INIT} °C"

# ==============================================================================
# PRE-FLIGHT CHECK 2: AMBIENT TEMPERATURE & HUMIDITY (BLE ThermoPro)
# ==============================================================================
if [ ! -s "$AMBIENT_SRC" ]; then
    echo "[-] PRE-FLIGHT FAILED: Ambient log not found or empty at $AMBIENT_SRC" >&2
    exit 1
fi
LAST_AMB_LINE=$(tail -n 1 "$AMBIENT_SRC")
LAST_AMB_TS=$(echo "$LAST_AMB_LINE" | awk -F',' '{printf "%d", $1}' 2>/dev/null || echo 0)
NOW_TS=$(date +%s)
AMB_AGE=$(( NOW_TS - LAST_AMB_TS ))
if [ "$AMB_AGE" -gt 180 ]; then
    echo "[-] PRE-FLIGHT FAILED: Ambient log ($AMBIENT_SRC) is stale (last sample ${AMB_AGE}s ago > 180s)." >&2
    echo "    Last line: $LAST_AMB_LINE" >&2
    exit 1
fi
echo "[+][Pre-Flight 2/3] Ambient Temperature & Humidity sensor OK (age=${AMB_AGE}s): $LAST_AMB_LINE"

# ==============================================================================
# PRE-FLIGHT CHECK 3: WALL-PLUG POWER METER (Tapo P115 at 1 Hz)
# ==============================================================================
cat > "$OUT/tapo_rejuv_mon.py" <<'PYEOF'
import asyncio, os, sys, time
from tapo import ApiClient

async def monitor():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    print('timestamp,power_w')
    sys.stdout.flush()
    while True:
        try:
            energy = await device.get_current_power()
            print(f'{time.time():.3f},{energy.current_power}')
            sys.stdout.flush()
        except Exception as e:
            print(f'err,{e}', file=sys.stderr)
        await asyncio.sleep(1)

asyncio.run(monitor())
PYEOF

"$PY" "$OUT/tapo_rejuv_mon.py" > "$OUT/power.csv" 2> "$OUT/power.err" &
MON_PID=$!

# Start 1 Hz System + Thermal + Ambient Monitor
cat > "$OUT/sys_rejuv_mon.sh" <<SHEOF
#!/bin/bash
echo "timestamp,cpu_temp_c,ambient_c,humidity_pct,freq_khz_max,freq_khz_pcore_max,mem_used_mb,page_cache_mb,runner_rss_kb"
while true; do
    ts=\$(date +%s.%3N)
    ctemp=\$(sensors 2>/dev/null | awk '/Package id 0:|Core 0:/ {gsub(/[+°C]/,"",\$0); for(i=1;i<=NF;i++) if(\$i ~ /^[0-9]+\.[0-9]+\$/){print \$i; exit}}')
    amb_line=\$(tail -n 1 "$AMBIENT_SRC" 2>/dev/null)
    amb_c=\$(echo "\$amb_line" | awk -F',' '{print \$2}')
    hum_pct=\$(echo "\$amb_line" | awk -F',' '{print \$3}')
    pmax=\$(cat /sys/devices/system/cpu/cpu{0..11}/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
    max=\$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
    mem_used=\$(free -m | awk '/Mem:/ {print \$3}')
    cached=\$(awk '/^Cached:/ {printf "%d", \$2/1024}' /proc/meminfo)
    rpid=\$(pgrep -f "ollama.*runner" | head -1)
    if [ -n "\$rpid" ] && [ -r "/proc/\$rpid/status" ]; then
        orss=\$(awk '/^VmRSS:/ {print \$2}' "/proc/\$rpid/status")
    else
        orss=0
    fi
    echo "\$ts,\${ctemp:-0},\${amb_c:-0},\${hum_pct:-0},\${max:-0},\${pmax:-0},\${mem_used:-0},\${cached:-0},\${orss:-0}"
    sleep 1
done
SHEOF
chmod +x "$OUT/sys_rejuv_mon.sh"
"$OUT/sys_rejuv_mon.sh" > "$OUT/system_metrics.csv" 2>/dev/null &
SYS_PID=$!

cleanup() {
    kill "$MON_PID" 2>/dev/null
    kill "$SYS_PID" 2>/dev/null
    if [ -f "$AMBIENT_SRC" ]; then
        cp "$AMBIENT_SRC" "$OUT/ambient_ble_snapshot.csv" 2>/dev/null || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

sleep 5
POWER_LINES=$(wc -l < "$OUT/power.csv" 2>/dev/null || echo 0)
if [ "$POWER_LINES" -lt 2 ]; then
    echo "[-] PRE-FLIGHT FAILED: Tapo P115 power meter not answering; see $OUT/power.err" >&2
    head -5 "$OUT/power.err" >&2
    exit 1
fi
LAST_PWR=$(tail -n 1 "$OUT/power.csv")
echo "[+][Pre-Flight 3/3] Tapo P115 Power Meter OK: $LAST_PWR (W)"

EVENTS_CSV="$OUT/rejuvenation_events.csv"
echo "model,action,rep,t_action_start,t_action_done,t_first_token_done,action_s,reload_and_infer_s,total_cycle_s,prefill_tps,decode_tps,cpu_temp_c,ambient_c,humidity_pct,runner_pid_before,runner_pid_after,rss_before_kb,rss_after_kb,cached_before_mb,cached_after_mb" > "$EVENTS_CSV"

get_runner_pid() {
    pgrep -f "ollama.*runner" | head -1 || echo 0
}

get_runner_rss_kb() {
    local rpid
    rpid=$(pgrep -f "ollama.*runner" | head -1)
    if [ -n "$rpid" ] && [ -r "/proc/$rpid/status" ]; then
        awk '/^VmRSS:/ {print $2}' "/proc/$rpid/status"
    else
        echo 0
    fi
}

get_cached_mb() {
    awk '/^Cached:/ {printf "%d", $2/1024}' /proc/meminfo
}

evict_os_page_cache() {
    if [ "$EUID" -eq 0 ]; then
        sync && echo 3 > /proc/sys/vm/drop_caches
    else
        # Evict readable model blobs via POSIX_FADV_DONTNEED
        "$PY" - <<'PYEOF'
import glob, os
for root in ['/usr/share/ollama/.ollama/models/blobs', os.path.expanduser('~/.ollama/models/blobs')]:
    for p in glob.glob(os.path.join(root, 'sha256-*')):
        try:
            fd = os.open(p, os.O_RDONLY)
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            os.close(fd)
        except Exception:
            pass
PYEOF
    fi
}

run_single_prompt() {
    local model=$1
    curl -s http://localhost:11434/api/generate -d "{
        \"model\": \"$model\",
        \"prompt\": \"$PROMPT\",
        \"stream\": false,
        \"keep_alive\": \"60m\"
    }"
}

for MODEL in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "[*] Profiling Rejuvenation Costs for Model: $MODEL ($REPS reps)"
    echo "=========================================================="

    ollama pull "$MODEL" >/dev/null 2>&1
    run_single_prompt "$MODEL" >/dev/null
    run_single_prompt "$MODEL" >/dev/null
    sleep 3

    LAST_WARM_RESTART_S="3.0"

    for ACTION in "runner_restart_warm" "page_cache_drop" "runner_restart_cold" "idle_pause_control"; do
        echo "  -> Action: $ACTION"
        for REP in $(seq 1 "$REPS"); do
            run_single_prompt "$MODEL" >/dev/null
            sleep 2

            pid_before=$(get_runner_pid)
            rss_before=$(get_runner_rss_kb)
            cached_before=$(get_cached_mb)
            t_start=$(date +%s.%3N)

            case "$ACTION" in
                runner_restart_warm)
                    curl -s http://localhost:11434/api/generate \
                        -d "{\"model\":\"$MODEL\",\"prompt\":\"x\",\"stream\":false,\"keep_alive\":0}" >/dev/null 2>&1
                    sleep 0.5
                    ;;
                page_cache_drop)
                    evict_os_page_cache
                    ;;
                runner_restart_cold)
                    curl -s http://localhost:11434/api/generate \
                        -d "{\"model\":\"$MODEL\",\"prompt\":\"x\",\"stream\":false,\"keep_alive\":0}" >/dev/null 2>&1
                    sleep 0.5
                    evict_os_page_cache
                    ;;
                idle_pause_control)
                    sleep "$LAST_WARM_RESTART_S"
                    ;;
            esac

            t_ready=$(date +%s.%3N)
            resp=$(run_single_prompt "$MODEL")
            t_done=$(date +%s.%3N)

            pid_after=$(get_runner_pid)
            rss_after=$(get_runner_rss_kb)
            cached_after=$(get_cached_mb)
            ctemp=$(sensors 2>/dev/null | awk '/Package id 0:|Core 0:/ {gsub(/[+°C]/,"",$0); for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.[0-9]+$/){print $i; exit}}')
            amb_line=$(tail -n 1 "$AMBIENT_SRC" 2>/dev/null)
            amb_c=$(echo "$amb_line" | awk -F',' '{print $2}')
            hum_pct=$(echo "$amb_line" | awk -F',' '{print $3}')

            prefill_tokens=$(echo "$resp" | jq -r '.prompt_eval_count // 0')
            prefill_dur_ns=$(echo "$resp" | jq -r '.prompt_eval_duration // 1')
            decode_tokens=$(echo "$resp" | jq -r '.eval_count // 0')
            decode_dur_ns=$(echo "$resp" | jq -r '.eval_duration // 1')

            prefill_tps=$(echo "scale=2; ($prefill_tokens * 1000000000) / $prefill_dur_ns" | bc)
            decode_tps=$(echo "scale=2; ($decode_tokens * 1000000000) / $decode_dur_ns" | bc)

            action_s=$(echo "scale=3; $t_ready - $t_start" | bc)
            reload_s=$(echo "scale=3; $t_done - $t_ready" | bc)
            total_s=$(echo "scale=3; $t_done - $t_start" | bc)

            if [ "$ACTION" = "runner_restart_warm" ]; then
                LAST_WARM_RESTART_S="$total_s"
            fi

            echo "$MODEL,$ACTION,$REP,$t_start,$t_ready,$t_done,$action_s,$reload_s,$total_s,$prefill_tps,$decode_tps,${ctemp:-0},${amb_c:-0},${hum_pct:-0},${pid_before:-0},${pid_after:-0},$rss_before,$rss_after,$cached_before,$cached_after" >> "$EVENTS_CSV"
            echo "     [rep $REP/$REPS] action=${action_s}s | reload+infer=${reload_s}s | total=${total_s}s | decode=${decode_tps} tps | PID:${pid_before}->${pid_after} | T_cpu=${ctemp}°C | T_amb=${amb_c}°C (${hum_pct}%)"
            sleep 3
        done
    done

    curl -s http://localhost:11434/api/generate \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"x\",\"stream\":false,\"keep_alive\":0}" >/dev/null 2>&1
    sleep 3
done

echo "[+] Rejuvenation Cost Profile Complete: $OUT"
