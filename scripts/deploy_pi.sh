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
UNIT_BLE=/etc/systemd/system/ambient-logger-ble.service

# local path                        remote path
FILES=(
  "src/ambient_logger.py              $REMOTE_DIR/src/ambient_logger.py"
  "scripts/ambient-logger.service     $UNIT"
  "src/ambient_logger_ble.py          $REMOTE_DIR/src/ambient_logger_ble.py"
  "scripts/ambient-logger-ble.service $UNIT_BLE"
  "scripts/ble_probe_thermopro.py     $REMOTE_DIR/scripts/ble_probe_thermopro.py"
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

    case "$remote_f" in
      /etc/systemd/system/*)
        unit_name=$(basename "$remote_f")
        scp -q -o BatchMode=yes "$local_f" "$PI:/tmp/$unit_name" \
          && ssh -o BatchMode=yes "$PI" "sudo install -m 0644 /tmp/$unit_name '$remote_f' && rm -f /tmp/$unit_name" \
          || { echo "[!] could not install $unit_name (needs sudo on the Pi)" >&2; exit 1; }
        restart_unit=1
        ;;
      *)
        ssh -o BatchMode=yes "$PI" "mkdir -p '$(dirname "$remote_f")'"
        scp -q -o BatchMode=yes "$local_f" "$PI:$remote_f" \
          || { echo "[!] copy failed: $local_f" >&2; exit 1; }
        restart_logger=1
        ;;
    esac
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
    # Restart only the units that exist. The BLE logger is a separate unit so
    # the two sensors can run side by side while the new one earns trust; a Pi
    # that has only ever had the I2C one must not fail here.
    echo "[+] restarting the loggers that are installed"
    ssh -o BatchMode=yes "$PI" '
      for u in ambient-logger ambient-logger-ble; do
        if systemctl list-unit-files "$u.service" >/dev/null 2>&1 \
           && [ -f "/etc/systemd/system/$u.service" ]; then
          sudo systemctl restart "$u" && echo "    restarted $u"
        fi
      done'
    sleep 4
fi

echo "[+] verifying"
ssh -o BatchMode=yes "$PI" 'bash -s' <<'REMOTE'
for pair in "ambient-logger /home/magnuspi/ambient.csv" \
            "ambient-logger-ble /home/magnuspi/ambient_ble.csv"; do
    set -- $pair; u=$1; f=$2
    [ -f "/etc/systemd/system/$u.service" ] || continue
    printf "    %-20s %s / %s\n" "$u" "$(systemctl is-active $u)" "$(systemctl is-enabled $u)"
    if [ -f "$f" ]; then
        before=$(wc -l < "$f"); sleep 5; after=$(wc -l < "$f")
        printf "      log: %s lines, +%s in 5 s\n" "$after" "$((after-before))"
        [ "$after" -gt "$before" ] || echo "      [!] not growing -- check journalctl -u $u"
    else
        echo "      [!] $f does not exist yet"
    fi
done
REMOTE

echo "[+] done. Collect the data with ./scripts/collect_ambient.sh <campaign-dir>"
