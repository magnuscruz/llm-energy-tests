#!/bin/bash
# ==============================================================================
# Autonomous Queue Scheduler: Waits for Test A, then runs Test B and Test C
# ==============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

LOG="$REPO/queue_tests_b_c.log"
exec > >(tee -a "$LOG") 2>&1

echo "=========================================================="
echo "[*] QUEUE WATCHER ACTIVE AT: $(date -u -Is)"
echo "[*] Monitoring Test A (jemalloc)..."
echo "=========================================================="

# Wait for Test A to finish
while pgrep -f "run_paper3_test_a_jemalloc" >/dev/null 2>&1; do
    sleep 10
done

echo "[+] Test A finished at: $(date -u -Is)"
echo "[*] Entering 180-second thermal & resource cooldown..."
sleep 180

# Run Test B (Qwen 2.5 0.5B - 12h)
echo "=========================================================="
echo "[*] LAUNCHING TEST B: Multi-Model Architecture (qwen2.5:0.5b - 12h)"
echo "[*] Start Time: $(date -u -Is)"
echo "=========================================================="
./scripts/run_paper3_test_b_multimodel.sh "qwen2.5:0.5b" 12h
echo "[+] Test B Completed at: $(date -u -Is)"

echo "[*] Entering 180-second thermal & resource cooldown..."
sleep 180

# Run Test C (Cold Rejuvenation L4 Calibration - 5 trials)
echo "=========================================================="
echo "[*] LAUNCHING TEST C: Cold Rejuvenation Energy Calibration L4"
echo "[*] Start Time: $(date -u -Is)"
echo "=========================================================="
./scripts/run_paper3_test_c_cold_restart.sh "phi3:mini" 5
echo "[+] Test C Completed at: $(date -u -Is)"

echo "=========================================================="
echo "[+] COMPLETE PIPELINE (A -> B -> C) FINISHED AT: $(date -u -Is)"
echo "=========================================================="

