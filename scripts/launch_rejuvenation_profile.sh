#!/usr/bin/env bash
set -euo pipefail

NODE="ubuntu@ubuntu-llm"
LOCAL_SCRIPT="/home/magnus/git/llm-energy-tests/scripts/profile_rejuvenation_cost.sh"
REMOTE_SCRIPT="/home/ubuntu/git/llm-energy-tests/scripts/profile_rejuvenation_cost.sh"
REMOTE_LOG="/home/ubuntu/git/llm-energy-tests/rejuvenation_profile.log"

echo "[1/3] Copying profile_rejuvenation_cost.sh to $NODE..."
scp -o BatchMode=yes "$LOCAL_SCRIPT" "$NODE:$REMOTE_SCRIPT"

echo "[2/3] Launching profile_rejuvenation_cost.sh (5 reps) in background on $NODE..."
ssh -o BatchMode=yes "$NODE" "chmod +x $REMOTE_SCRIPT && nohup $REMOTE_SCRIPT 5 > $REMOTE_LOG 2>&1 < /dev/null &"

echo "[3/3] Waiting 15s to verify Pre-Flight checks and initial progress..."
sleep 15
ssh -o BatchMode=yes "$NODE" "cat $REMOTE_LOG && echo '--- ACTIVE PIDS ---' && pgrep -af 'profile_rejuvenation_cost|tapo_rejuv_mon|sys_rejuv_mon'"
