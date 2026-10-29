#!/usr/bin/env bash
# ==============================================================================
# Pre-Flight Telemetry & Node Readiness Check (Agenda A4)
# Verifies on ubuntu-llm:
#   1. Node reachability & whether any benchmark/collector is currently active
#   2. CPU temperature sensor (lm-sensors)
#   3. Ambient temperature & humidity logger (ambient-logger-ble / ambient_ble.csv)
#   4. Out-of-band wall-plug power meter (TP-Link Tapo P115 at 192.168.0.200)
# ==============================================================================
set -uo pipefail

NODE="${1:-}"
if [ -z "$NODE" ]; then
    for cand in "ubuntu@ubuntu-llm" "ubuntu@192.168.0.205"; do
        if ssh -o BatchMode=yes -o ConnectTimeout=5 "$cand" 'exit' 2>/dev/null; then
            NODE="$cand"
            break
        fi
    done
    NODE="${NODE:-ubuntu@ubuntu-llm}"
fi
echo "[*] Connecting to edge node ($NODE) to verify telemetry streams..."

ssh -o BatchMode=yes -o ConnectTimeout=8 "$NODE" 'bash -s' <<'EOF'
set -u
echo "=== 1. ACTIVE PROCESSES & DISK HEADROOM ==="
running=$(pgrep -fc "[t]apo_monitor|[f]req_monitor|[r]un_benchmark_pair|[p]rofile_" 2>/dev/null) || running=0
echo "Active benchmark/collector processes: $running"
df -h /home/ubuntu/git/llm-energy-tests/logs 2>/dev/null || df -h /

echo ""
echo "=== 2. CPU TEMPERATURE (lm-sensors) ==="
sensors 2>/dev/null | grep -E "Package id 0:|Core 0:" || echo "[!] sensors command returned no Core/Package temperature"

echo ""
echo "=== 3. AMBIENT TEMPERATURE & HUMIDITY (BLE ThermoPro) ==="
systemctl is-active ambient-logger-ble 2>/dev/null && echo "Service ambient-logger-ble: ACTIVE" || echo "Service ambient-logger-ble: INACTIVE"
if [ -f "$HOME/ambient_ble.csv" ]; then
    lines=$(wc -l < "$HOME/ambient_ble.csv")
    last=$(tail -n 1 "$HOME/ambient_ble.csv")
    last_ts=$(echo "$last" | awk -F',' '{printf "%d", $1}' 2>/dev/null || echo 0)
    age=$(( $(date +%s) - last_ts ))
    echo "File: $HOME/ambient_ble.csv ($lines lines, last sample ${age}s ago)"
    echo "Latest reading (ts,temp_c,humidity_pct): $last"
else
    echo "[!] $HOME/ambient_ble.csv not found on node"
fi

echo ""
echo "=== 4. WALL-PLUG POWER METER (Tapo P115) ==="
cd /home/ubuntu/git/llm-energy-tests || exit 1
if [ -f .env ]; then
    set -a; . ./.env; set +a
    PY=$([ -x venv/bin/python3 ] && echo "./venv/bin/python3" || echo "./.venv/bin/python3")
    "$PY" - <<'PYEOF'
import asyncio, os, time
from tapo import ApiClient

async def check():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    p = await device.get_current_power()
    print(f"Tapo P115 ({os.environ['TAPO_IP']}) OK -> Current Power: {p.current_power} W at ts={int(time.time())}")

asyncio.run(check())
PYEOF
else
    echo "[!] .env not found in /home/ubuntu/git/llm-energy-tests"
fi
EOF
