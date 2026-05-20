#!/bin/bash
# DEI Research Benchmark - LLM Software Aging & Thermal Leakage Tool
# This script runs a pairwise benchmark comparing a dense model (LLaMA 3.1 8B) against a MoE model (DeepSeek-V2 Lite) under identical conditions.
# sudo nohup ./scripts/run_benchmark_pair.sh 172800 --throttle 87.5 > benchmark_run_pair.log 2>&1 &

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

# 2. Updated Configuration: $1 as duration (in seconds) Run & Model Pair (Dense vs MoE)
DURATION_SECONDS=$1
WARMUP_DURATION=600 # 10 
MODELS=("qwen2.5:0.5b" "phi3:mini" "llama3.1:8b" "deepseek-v2:lite") # Updated to include both the dense vs MoE pair and the smaller models for a more comprehensive comparison. You can adjust this list based on your specific benchmarking goals.
#MODELS=("qwen2.5:0.5b") # Updated to match the models in your original script, but you can switch back to the dense vs MoE pair if desired
PROJECT_ROOT="/home/ubuntu/git/llm-energy-tests"
LOG_DIR="$PROJECT_ROOT/logs/$(date +%Y-%m-%d)"
WARMUP_DIR="${LOG_DIR}/warmup_logs"
AGING_DIR="${LOG_DIR}/deep_aging"

# Tapo P115 Config
export TAPO_USER="magnuscruz@gmail.com"
export TAPO_PASS="***REMOVIDO***"
export TAPO_IP="192.168.0.100"
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
    # Forcibly unload both models from VRAM
    ollama stop ${MODELS} 2>/dev/null
    ollama stop ${MODELS} 2>/dev/null
    sync && echo 3 > /proc/sys/vm/drop_caches
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

# 5. Hardware Mitigation (Using your existing cpupower logic)
apply_throttling() {
    if [ "$THROTTLE_ENABLED" = true ]; then
        echo "[Config] Setting CPU to PowerSave/Low Frequency (${THROTTLE_PERCENTAGE}% limit)..."
        cpupower frequency-set -g powersave > /dev/null
        MAX_FREQ=$(cpupower frequency-info -l | awk 'END{print $2}')
        CAP_FREQ=$(echo "$MAX_FREQ * $THROTTLE_PERCENTAGE / 100" | bc | cut -d. -f1)
        cpupower frequency-set -u ${CAP_FREQ}kHz > /dev/null
    else
        echo "Running Fully Unthrottled."
        cpupower frequency-set -g performance >/dev/null 2>&1
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
        print('Time,Watts')
        sys.stdout.flush()
        while True:
            energy = await device.get_current_power()
            # Log the long timestamp in seconds and current power in watts
            timestamp = int(time.time())
            print(f'{timestamp},{energy.current_power}')
            sys.stdout.flush()
            await asyncio.sleep(1)
    except Exception as e:
        pass

if __name__ == "__main__":
    asyncio.run(monitor())
EOF

start_tapo_monitor() {
    export TARGET_DIR=$1
    local SAFE_MODEL=${2//:/_}
    local TIMESTAMP=$3
    local OUT_FILE="${TARGET_DIR}/${SAFE_MODEL}_${TIMESTAMP}_physical.csv"
    $PYTHON_VENV tapo_monitor_temp.py > "$OUT_FILE" 2>/dev/null &
    TAPO_PID=$!
}

# 6. Updated Phase-Aware Inference Loop
run_inference_loop() {
    local model=$1
    local log_file=$2
    local duration=$3
    local end_time=$(( $(date +%s) + duration ))

    # New headers splitting Prefill and Decode phases
    echo "timestamp,model,cpu_temp,ram_used_mb,prefill_tps,decode_tps,prefill_dur_s,decode_dur_s" > "$log_file"

    while [ $(date +%s) -lt $end_time ]; do
        local current_time=$(date +%s)

        # Capture System Metrics (using your existing top/free/sensors logic)
        local cpu_temp=$(sensors | awk '/Core 0/ {print $3}' | tr -d '+°C')
        local ram_used=$(free -m | awk '/Mem:/ {print $3}')

        # Send request using your standard benchmark prompt
        local response=$(curl -s http://localhost:11434/api/generate -d '{
            "model": "'"$model"'",
            "prompt": "Analyze the implications of software aging on distributed edge network reliability.",
            "stream": false
        }')

        # Extract Phase-Aware Metrics using jq 
        local prefill_tokens=$(echo "$response" | jq -r '.prompt_eval_count // 0')
        local prefill_dur_ns=$(echo "$response" | jq -r '.prompt_eval_duration // 1')
        local decode_tokens=$(echo "$response" | jq -r '.eval_count // 0')
        local decode_dur_ns=$(echo "$response" | jq -r '.eval_duration // 1')

        # Calculate TPS (Converting nanoseconds to seconds via * 10^9)
        local prefill_tps=$(echo "scale=2; ($prefill_tokens * 1000000000) / $prefill_dur_ns" | bc)
        local decode_tps=$(echo "scale=2; ($decode_tokens * 1000000000) / $decode_dur_ns" | bc)

        # Convert durations from nanoseconds to seconds
        local prefill_dur_s=$(echo "scale=6; $prefill_dur_ns / 1000000000" | bc)
        local decode_dur_s=$(echo "scale=6; $decode_dur_ns / 1000000000" | bc)

        # Log the aggregated metrics
        echo "$current_time,$model,$cpu_temp,$ram_used,$prefill_tps,$decode_tps,$prefill_dur_s,$decode_dur_s" >> "$log_file"
    done
}

# 7. Main Execution Pipeline
apply_throttling

for MODEL in "${MODELS[@]}"; do
    echo "=========================================================="
    echo "Preparing to Benchmark: $MODEL"
    echo "=========================================================="
    echo "Warmup Phase: Running for $WARMUP_DURATION seconds to stabilize performance..."

    # Pull the latest model version to ensure consistency
    ollama pull "$MODEL"
    
    TIMESTAMP=$(date +%H%M%S)
    echo "[*] Executing ${WARMUP_DURATION}s Warm-Up Phase..."
    
    DURATION_HOURS=$(echo "scale=2; $DURATION_SECONDS / 3600" | bc)

    start_tapo_monitor "$WARMUP_DIR" "$MODEL" "$DURATION_HOURS"h_warmup
    run_inference_loop "$MODEL" "$WARMUP_DIR/${MODEL//:/_}_warmup.csv" "$WARMUP_DURATION" &
    INF_PID=$!
    wait $INF_PID
    kill $TAPO_PID 2>/dev/null
        
    echo "Warm-Up Complete. Starting ${DURATION_HOURS}-hour Continuous Evaluation for $MODEL..."
    
    # Ensure a pristine environment before the XX-hour run begins
    rejuvenate_inference_engine
    
    TIMESTAMP=$(date +%H%M%S)
    echo "----------------------------------------------------------"
    echo "[*] Executing Continuous Deep Aging Phase ($TEST_DURATION seconds)..."


    LOG_FILE="$LOG_DIR/deep_aging/${MODEL//:/_}_${DURATION_HOURS}h_inference.csv"
    echo "Starting ${DURATION_HOURS}-hour continuous evaluation. Logging to $LOG_FILE"

    start_tapo_monitor "$AGING_DIR" "$MODEL" "$DURATION_HOURS"h_aging
    run_inference_loop "$MODEL" "$LOG_FILE" "$DURATION_SECONDS" &
    INF_PID=$!
    wait $INF_PID

    # Terminate the power logger and explicitly unload the model from VRAM
    kill $TAPO_PID 2>/dev/null

    # Clean up the model from memory to prevent interference with subsequent runs
    ollama stop "$MODEL" 2>/dev/null || docker stop ollama 2>/dev/null
    ollama rm "$MODEL" 2>/dev/null || docker rm ollama 2>/dev/null
    echo "Completed ${DURATION_HOURS} hours for $MODEL."
done

echo "Model Pair Benchmarking Complete."
cpupower frequency-set -g performance >/dev/null 2>&1

rm -f tapo_monitor_temp.py
echo "Benchmark Suite Finished Successfully."
cleanup