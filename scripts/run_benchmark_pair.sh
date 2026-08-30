#!/bin/bash
# DEI Research Benchmark - LLM Software Aging & Thermal Leakage Tool
# Runs the 4-model benchmark (dense vs MoE) under identical conditions.
# Re-run of the 50% condition:
#   sudo nohup ./scripts/run_benchmark_pair.sh 172800 --throttle 50 > benchmark_run_pair.log 2>&1 &

# 1. Enforce Root Privileges for Governor and Cache control
if [ "$EUID" -ne 0 ]; then
    echo -e "\n[-] ERROR: This benchmark requires root privileges."
    echo "[-] Proactive Rejuvenation and Thermal Throttling need deep system access."
    echo -e "[*] Please run the script using sudo:\n    sudo $0 $@"
    exit 1
fi

# --- Argument Parsing ---
THROTTLE_ENABLED=false
THROTTLE_PERCENTAGE=50

if [[ "$2" == "--throttle" ]]; then
    THROTTLE_ENABLED=true
    THROTTLE_PERCENTAGE=$3
    echo "[!] Throttling ENABLED at ${THROTTLE_PERCENTAGE}% for this run."
fi

if [ -z "$1" ]; then
    echo "Usage: sudo $0 <duration_in_seconds> [--throttle <percentage>]"
    exit 1
fi

# 2. Configuration
DURATION_SECONDS=$1
WARMUP_DURATION=600 # 10 min
MODELS=("qwen2.5:0.5b" "phi3:mini" "llama3.1:8b" "deepseek-v2:lite")
PROJECT_ROOT="/home/ubuntu/git/llm-energy-tests"
LOG_DIR="$PROJECT_ROOT/logs/$(date +%Y-%m-%d)"
WARMUP_DIR="${LOG_DIR}/warmup_logs"
AGING_DIR="${LOG_DIR}/deep_aging"

# --------------------------------------------------------------------------
# CAP BASE FREQUENCY (kHz) - FIXED AND EXPLICIT.
# The i5-13500 is a hybrid CPU: P-cores max 4,800,000 kHz, E-cores max
# 3,500,000 kHz. `cpupower frequency-info -l | awk 'END{...}'` parsed the
# LAST core listed (an E-core), silently making 3,500,000 the base of all
# previous throttled campaigns. We keep that base EXPLICITLY so the re-run
# of the 50% condition is commensurable with the existing 62.5/75/87.5%
# datasets (cap ladder: 1750/2188/2625/3063 MHz).
BASE_FREQ_KHZ=3500000
# --------------------------------------------------------------------------

# Tapo P115 Config - Load from .env file and export variables to child processes
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "Error: .env file not found at $PROJECT_ROOT/.env"
    exit 1
fi
PYTHON_VENV="$PROJECT_ROOT/venv/bin/python3"

# --- Dependency Check ---
for cmd in jq sensors powerstat bc curl; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is not installed. Please install it to continue."
        exit 1
    fi
done

mkdir -p "$WARMUP_DIR"
mkdir -p "$AGING_DIR"

# 3. Robust Cleanup Trap
cleanup() {
    echo "Interrupt received. Cleaning up..."
    pkill -f tapo_monitor_temp.py
    pkill -f freq_monitor_temp.sh
    ollama stop ${MODELS} 2>/dev/null
    ollama stop ${MODELS} 2>/dev/null
    sync && echo 3 > /proc/sys/vm/drop_caches
    cpupower frequency-set -u ${BASE_FREQ_KHZ}kHz >/dev/null 2>&1  # lift any cap remnant
    cpupower frequency-set -g performance >/dev/null 2>&1
    exit 0
}
trap cleanup SIGINT SIGTERM

# 4. Proactive Rejuvenation (Zero-State Reset)
rejuvenate_inference_engine() {
    echo "Performing Proactive Software Rejuvenation (Zero-State Reset)..."
    systemctl restart ollama
    sleep 5
    sync && echo 3 > /proc/sys/vm/drop_caches
    sleep 5
}

# 5. Hardware Mitigation + VERIFICATION
apply_throttling() {
    if [ "$THROTTLE_ENABLED" = true ]; then
        CAP_FREQ=$(echo "$BASE_FREQ_KHZ * $THROTTLE_PERCENTAGE / 100" | bc | cut -d. -f1)
        echo "[Config] Governor=powersave, cap=${THROTTLE_PERCENTAGE}% of ${BASE_FREQ_KHZ} kHz -> ${CAP_FREQ} kHz"
        cpupower frequency-set -g powersave > /dev/null
        cpupower frequency-set -u ${CAP_FREQ}kHz > /dev/null
    else
        echo "Running Fully Unthrottled."
        cpupower frequency-set -g performance >/dev/null 2>&1
    fi
    verify_throttling
}

# Reads back what the kernel actually applied and logs it. Aborts if the
# effective cap deviates from the requested one (prevents a repeat of the
# silently mis-throttled campaign).
verify_throttling() {
    local p_max e_max gov epp
    p_max=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
    e_max=$(cat /sys/devices/system/cpu/cpu12/cpufreq/scaling_max_freq 2>/dev/null || echo "n/a")
    gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
    epp=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null || echo "n/a")
    echo "[Verify] scaling_max_freq: P-core=${p_max} E-core=${e_max} | governor=${gov} | EPP=${epp}"
    {
        echo "date=$(date -Is)"
        echo "throttle_enabled=${THROTTLE_ENABLED}"
        echo "throttle_percentage=${THROTTLE_PERCENTAGE}"
        echo "base_freq_khz=${BASE_FREQ_KHZ}"
        echo "requested_cap_khz=${CAP_FREQ:-none}"
        echo "applied_pcore_max_khz=${p_max}"
        echo "applied_ecore_max_khz=${e_max}"
        echo "governor=${gov}"
        echo "epp=${epp}"
        echo "ollama_version=$(ollama --version 2>/dev/null | head -1)"
        echo "kernel=$(uname -r)"
        # Model digests, one line per model. Without them, a change to a model
        # snapshot between campaigns is indistinguishable from any other change,
        # and a difference in behaviour months apart cannot be attributed.
        # "ollama list" prints the digest prefix in its ID column.
        ollama list 2>/dev/null | awk 'NR>1 && $1!="" {
            name=$1; gsub(/[:.\/]/,"_",name); print "model_digest_" name "=" $2 }'
    } >> "$LOG_DIR/run_config.log"
    if [ "$THROTTLE_ENABLED" = true ] && [ "$p_max" != "$CAP_FREQ" ]; then
        echo "[-] FATAL: applied cap (${p_max}) != requested cap (${CAP_FREQ}). Aborting."
        exit 1
    fi
}

# ==============================================================================
# ASYNCHRONOUS TAPO PHYSICAL LOGGER
# ==============================================================================
cat << 'EOF' > tapo_monitor_temp.py
import asyncio, time, sys, os
from tapo import ApiClient

async def monitor():
    try:
        client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
        device = await client.p115(os.environ['TAPO_IP'])
        print('timestamp,power_w')
        sys.stdout.flush()
        while True:
            energy = await device.get_current_power()
            timestamp = int(time.time())
            print(f'{timestamp},{energy.current_power}')
            sys.stdout.flush()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error in Tapo monitoring: {e}", file=sys.stderr)
        pass

if __name__ == "__main__":
    asyncio.run(monitor())
EOF

# ==============================================================================
# ASYNCHRONOUS CPU FREQUENCY LOGGER (1 Hz)
# Written via quoted heredoc: no escaping pitfalls inside awk.
# freq_khz_max       = fastest core overall (loaded core)
# freq_khz_mean      = mean across all logical CPUs
# freq_khz_pcore_max = fastest P-core thread (cpu0-11 on the i5-13500)
# ==============================================================================
cat << 'EOF' > freq_monitor_temp.sh
#!/bin/bash
echo "timestamp,freq_khz_max,freq_khz_mean,freq_khz_pcore_max"
while true; do
    ts=$(date +%s)
    freqs=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null)
    if [ -z "$freqs" ]; then
        echo "$ts,0,0,0"
    else
        max=$(printf "%s\n" $freqs | sort -n | tail -1)
        mean=$(printf "%s\n" $freqs | awk '{s+=$1} END {printf "%d", s/NR}')
        pmax=$(cat /sys/devices/system/cpu/cpu{0..11}/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
        echo "$ts,$max,$mean,${pmax:-0}"
    fi
    sleep 1
done
EOF
chmod +x freq_monitor_temp.sh

start_tapo_monitor() {
    local TARGET_DIR=$1
    local SAFE_MODEL=${2//:/_}
    local TIMESTAMP=$3
    local OUT_FILE="${TARGET_DIR}/${SAFE_MODEL}_${TIMESTAMP}_physical.csv"
    local ERR_FILE="${TARGET_DIR}/${SAFE_MODEL}_${TIMESTAMP}_physical.err"
    $PYTHON_VENV tapo_monitor_temp.py > "$OUT_FILE" 2> "$ERR_FILE" &
    TAPO_PID=$!
}

start_freq_monitor() {
    local TARGET_DIR=$1
    local SAFE_MODEL=${2//:/_}
    local TIMESTAMP=$3
    local OUT_FILE="${TARGET_DIR}/${SAFE_MODEL}_${TIMESTAMP}_freq.csv"
    ./freq_monitor_temp.sh > "$OUT_FILE" 2>/dev/null &
    FREQ_PID=$!
}

# 6. Phase-Aware Inference Loop
run_inference_loop() {
    local model=$1
    local log_file=$2
    local duration=$3
    local end_time=$(( $(date +%s) + duration ))

    # NOTE: scaling_cur_freq here is sampled BETWEEN requests (idle ramp-down);
    # the sustained under-load frequency comes from the 1 Hz *_freq.csv logger.
    echo "timestamp,model,cpu_temp,ram_used_mb,scaling_cur_freq,prefill_tps,decode_tps,prefill_dur_s,decode_dur_s" > "$log_file"

    while [ $(date +%s) -lt $end_time ]; do
        local current_time=$(date +%s)

        local cpu_temp=$(sensors | awk '/Core 0/ {print $3}' | tr -d '+°C')
        local ram_used=$(free -m | awk '/Mem:/ {print $3}')
        local scaling_cur_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 0)

        local response=$(curl -s http://localhost:11434/api/generate -d '{
            "model": "'"$model"'",
            "prompt": "Analyze the implications of software aging on distributed edge network reliability.",
            "stream": false
        }')

        local prefill_tokens=$(echo "$response" | jq -r '.prompt_eval_count // 0')
        local prefill_dur_ns=$(echo "$response" | jq -r '.prompt_eval_duration // 1')
        local decode_tokens=$(echo "$response" | jq -r '.eval_count // 0')
        local decode_dur_ns=$(echo "$response" | jq -r '.eval_duration // 1')

        local prefill_tps=$(echo "scale=2; ($prefill_tokens * 1000000000) / $prefill_dur_ns" | bc)
        local decode_tps=$(echo "scale=2; ($decode_tokens * 1000000000) / $decode_dur_ns" | bc)
        local prefill_dur_s=$(echo "scale=6; $prefill_dur_ns / 1000000000" | bc)
        local decode_dur_s=$(echo "scale=6; $decode_dur_ns / 1000000000" | bc)

        echo "$current_time,$model,$cpu_temp,$ram_used,$scaling_cur_freq,$prefill_tps,$decode_tps,$prefill_dur_s,$decode_dur_s" >> "$log_file"
    done
}

# 7. Main Execution Pipeline
for MODEL in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "Preparing to Benchmark: $MODEL"
    echo "=========================================================="

    # Re-apply and re-verify the cap before EVERY model: protects the
    # campaign against reboots or external governor changes mid-run.
    apply_throttling

    echo "Warmup Phase: Running for $WARMUP_DURATION seconds to stabilize performance..."
    ollama pull "$MODEL"

    TIMESTAMP=$(date +%H%M%S)
    echo "[*] Executing ${WARMUP_DURATION}s Warm-Up Phase..."
    DURATION_HOURS=$(echo "scale=2; $DURATION_SECONDS / 3600" | bc)

    start_tapo_monitor "$WARMUP_DIR" "$MODEL" "$DURATION_HOURS"h_warmup
    start_freq_monitor "$WARMUP_DIR" "$MODEL" "$DURATION_HOURS"h_warmup
    run_inference_loop "$MODEL" "$WARMUP_DIR/${MODEL//:/_}_warmup.csv" "$WARMUP_DURATION" &
    INF_PID=$!
    wait $INF_PID
    kill $TAPO_PID 2>/dev/null
    kill $FREQ_PID 2>/dev/null

    echo "Warm-Up Complete. Starting ${DURATION_HOURS}-hour Continuous Evaluation for $MODEL..."

    rejuvenate_inference_engine
    apply_throttling   # rejuvenation restarts services; re-verify the cap

    TIMESTAMP=$(date +%H%M%S)
    echo "----------------------------------------------------------"
    echo "[*] Executing Continuous Deep Aging Phase (${DURATION_SECONDS} seconds)..."

    LOG_FILE="$AGING_DIR/${MODEL//:/_}_${DURATION_HOURS}h_inference.csv"
    echo "Starting ${DURATION_HOURS}-hour continuous evaluation. Logging to $LOG_FILE"

    start_tapo_monitor "$AGING_DIR" "$MODEL" "$DURATION_HOURS"h
    start_freq_monitor "$AGING_DIR" "$MODEL" "$DURATION_HOURS"h
    run_inference_loop "$MODEL" "$LOG_FILE" "$DURATION_SECONDS" &
    INF_PID=$!
    wait $INF_PID

    kill $TAPO_PID 2>/dev/null
    kill $FREQ_PID 2>/dev/null

    ollama stop "$MODEL" 2>/dev/null || docker stop ollama 2>/dev/null
    ollama rm "$MODEL" 2>/dev/null || docker rm ollama 2>/dev/null
    echo "Completed ${DURATION_HOURS} hours for $MODEL."
done

echo "Model Pair Benchmarking Complete."
cpupower frequency-set -u ${BASE_FREQ_KHZ}kHz >/dev/null 2>&1
cpupower frequency-set -g performance >/dev/null 2>&1

rm -f tapo_monitor_temp.py freq_monitor_temp.sh
echo "Benchmark Suite Finished Successfully."
cleanup
