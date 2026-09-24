#!/bin/bash
# ==============================================================================
# Push the ambient logger to the Raspberry Pi and verify it landed.
#
# The Pi holds no clone of this repository: it is an SD card on a small board,
# and the repository carries a few hundred megabytes of campaign telemetry. What
# it holds instead is a copy of two files, which is how the two drift apart
# without anyone noticing. This script makes the copy a verified, repeatable
# step rather than a remembered one.
#
# It is safe to run at any time, including mid-campaign: it restarts the logger
# only when the logger itself changed, and a restart costs at most the samples
# taken while it was down, which appear in the data as an honest gap.
#
# Usage:
#   ./scripts/deploy_pi.sh            # find the Pi, sync, verify
#   ./scripts/deploy_pi.sh --check    # report drift, change nothing
#   PI_HOST=magnuspi@10.0.0.5 ./scripts/deploy_pi.sh
# ==============================================================================
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# Same candidate list as collect_ambient.sh, and for the same reason: the USB
# gadget link has never come up at this site, so it is tried last rather than
# first. See that script's header for what defaulting to it cost.
PI_CANDIDATES="${PI_HOST:-magnuspi@magnuspi.local magnuspi@192.168.0.158 magnuspi@192.168.7.2}"

PI=""
for cand in $PI_CANDIDATES; do
    if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new \
           "$cand" 'exit' 2>/dev/null; then
        PI="$cand"; echo "[+] reached the Pi at $cand"; break
    fi
    echo "[-] no answer from $cand"
done
[ -n "$PI" ] || { echo "[!] the Pi answered at none of: $PI_CANDIDATES" >&2
                  echo "    set PI_HOST, or check the Pi is powered and on the network" >&2
                  exit 1; }

REMOTE_DIR=/home/magnuspi/ambient
UNIT=/etc/systemd/system/ambient-logger.service

# local path                        remote path
FILES=(
  "src/ambient_logger.py            $REMOTE_DIR/src/ambient_logger.py"
  "scripts/ambient-logger.service   $UNIT"
)

drift=0
restart_logger=0
restart_unit=0

for pair in "${FILES[@]}"; do
    local_f=$(echo "$pair" | awk '{print $1}')
    remote_f=$(echo "$pair" | awk '{print $2}')
    [ -f "$local_f" ] || { echo "[!] missing locally: $local_f" >&2; exit 1; }

    want=$(md5sum < "$local_f" | cut -d' ' -f1)
    have=$(ssh -o BatchMode=yes "$PI" "md5sum < '$remote_f' 2>/dev/null | cut -d' ' -f1" 2>/dev/null)

    if [ "$want" = "$have" ]; then
        echo "    up to date   $local_f"
        continue
    fi

    drift=1
    if [ -z "$have" ]; then echo "    ABSENT on Pi  $remote_f"
    else                    echo "    DIFFERS       $remote_f  (Pi ${have:0:10}, repo ${want:0:10})"; fi

    [ "$CHECK_ONLY" = 1 ] && continue

    if [ "$remote_f" = "$UNIT" ]; then
        scp -q -o BatchMode=yes "$local_f" "$PI:/tmp/ambient-logger.service" \
          && ssh -o BatchMode=yes "$PI" "sudo install -m 0644 /tmp/ambient-logger.service '$UNIT' && rm -f /tmp/ambient-logger.service" \
          || { echo "[!] could not install the unit (needs sudo on the Pi)" >&2; exit 1; }
        restart_unit=1
    else
        ssh -o BatchMode=yes "$PI" "mkdir -p '$(dirname "$remote_f")'"
        scp -q -o BatchMode=yes "$local_f" "$PI:$remote_f" \
          || { echo "[!] copy failed: $local_f" >&2; exit 1; }
        restart_logger=1
    fi
    echo "    pushed        $remote_f"
done

if [ "$CHECK_ONLY" = 1 ]; then
    [ "$drift" = 0 ] && echo "[+] Pi matches the repository" || echo "[!] Pi has drifted; run without --check to sync"
    exit $drift
fi

if [ "$restart_unit" = 1 ]; then
    ssh -o BatchMode=yes "$PI" "sudo systemctl daemon-reload"
fi
if [ "$restart_logger" = 1 ] || [ "$restart_unit" = 1 ]; then
    echo "[+] restarting the logger"
    ssh -o BatchMode=yes "$PI" "sudo systemctl restart ambient-logger"
    sleep 4
fi

echo "[+] verifying"
ssh -o BatchMode=yes "$PI" 'bash -s' <<'REMOTE'
printf "    service: %s / %s\n" "$(systemctl is-active ambient-logger)" "$(systemctl is-enabled ambient-logger)"
f=/home/magnuspi/ambient.csv
if [ -f "$f" ]; then
    before=$(wc -l < "$f"); sleep 5; after=$(wc -l < "$f")
    printf "    log:     %s lines, +%s in 5 s\n" "$after" "$((after-before))"
    [ "$after" -gt "$before" ] || echo "    [!] the log is not growing"
else
    echo "    [!] $f does not exist"
fi
REMOTE

echo "[+] done. Collect the data with ./scripts/collect_ambient.sh <campaign-dir>"
