#!/usr/bin/env bash
# Set up BLE ambient logging ON THE NODE, in one command.
#
# Run this on the edge node itself, with the ThermoPro sensor nearby:
#
#     ./scripts/setup_ambient_node.sh            # check, probe, then ask
#     ./scripts/setup_ambient_node.sh --install  # same, but install at the end
#     ./scripts/setup_ambient_node.sh --check    # look only, change nothing
#
# It resolves the user, the paths and the python interpreter itself, so there
# is nothing to edit before running it.
#
# WHY THIS SITS ON THE NODE AND WHAT IT COSTS. Ambient measurement belongs
# outside the machine under test, and the Pi was that outside. Running it here
# instead puts a second collector inside the measured envelope, beside the 1 Hz
# power poll that is already there. Two things keep the cost small and, more
# importantly, CONSTANT across scenarios so that it cancels in every comparison:
# the scan is passive, and the radio is only on for a few seconds a minute.
# Constant is what matters; zero was never on offer once the collector moved in.
set -euo pipefail

MODE=ask
case "${1:-}" in
  --install) MODE=install ;;
  --check)   MODE=check ;;
  "")        ;;
  *) echo "usage: $0 [--install|--check]" >&2; exit 2 ;;
esac

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
USER_NAME=$(id -un)

LOG=${AMBIENT_LOG:-$HOME/ambient_ble.csv}
UNIT=/etc/systemd/system/ambient-logger-ble.service
# Prefer the repository's venv if there is one, because that is where the rest
# of the project's dependencies live and what systemd will be pointed at. Fall
# back to the system interpreter. Override with AMBIENT_PYTHON.
if [ -n "${AMBIENT_PYTHON:-}" ]; then PY=$AMBIENT_PYTHON
elif [ -x "$REPO/.venv/bin/python3" ]; then PY="$REPO/.venv/bin/python3"
else PY=$(command -v python3); fi
# Inside a venv, --user is both wrong and refused.
if "$PY" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)'; then
    PIP_TARGET_FLAG=""
else
    PIP_TARGET_FLAG="--user"
fi
INTERVAL=${AMBIENT_INTERVAL:-60}
WINDOW=${AMBIENT_SCAN_WINDOW:-8}
# Bind to one sensor by a substring of its advertised name, e.g. C505 for
# "TP351S (C505)". Left empty, the logger takes any TP35/TP39 device in range,
# which is right until a second one is ever within a few metres.
NAME=${AMBIENT_NAME:-}
NAME_ARG=""
[ -n "$NAME" ] && NAME_ARG=" --name $NAME"

say() { printf '%s\n' "$*"; }
ok()  { printf '  [ok]   %s\n' "$*"; }
bad() { printf '  [!]    %s\n' "$*"; }

say "[1/6] the machine"
say "      repo=$REPO  user=$USER_NAME  python=$PY"
say "      log=$LOG  interval=${INTERVAL}s  radio on ${WINDOW}s per interval"
if [ -n "$NAME" ]; then
    say "      bound to the sensor whose name contains '$NAME'"
else
    say "      not bound to a sensor: any TP35/TP39 in range will be logged."
    say "      Set AMBIENT_NAME=C505 (or similar) to pin it to one."
fi

say "[1b/6] nothing in flight"
# Starting a radio scan on the machine under test in the middle of a campaign
# perturbs the thing being measured. Refuse rather than ask.
#
# The bracket trick matters: a plain `pgrep -f tapo_monitor_temp.py` matches
# its OWN command line when run over SSH, because the pattern appears there.
# "[t]apo..." cannot match the literal string "[t]apo...", so only real
# processes are found. This has produced a false alarm in this project twice.
# `pgrep -c` and `grep -c` both PRINT 0 and EXIT 1 when they match nothing, so
# `|| echo 0` appends a second value and the variable becomes "0\n0", which is
# neither empty nor a number. Assign, then correct on failure.
running=$(pgrep -fc "[t]apo_monitor_temp.py|[f]req_monitor_temp.sh|[r]un_benchmark_pair.sh" 2>/dev/null) || running=0
loaded=$(ollama ps 2>/dev/null | sed 1d | grep -c .) || loaded=0
running=${running:-0}; loaded=${loaded:-0}
if [ "$running" -gt 0 ] || [ "$loaded" -gt 0 ]; then
    bad "a campaign looks active ($running collector(s), $loaded model(s) resident)"
    bad "installing a BLE scan now would perturb it. Wait for it to finish."
    exit 1
fi
ok "no campaign collectors, no model resident"

say "[2/6] bluetooth"
fail=0
if [ ! -d /sys/class/bluetooth ]; then
    bad "no /sys/class/bluetooth -- this kernel has no Bluetooth stack"; fail=1
else
    adapters=$(ls /sys/class/bluetooth 2>/dev/null | tr '\n' ' ')
    [ -n "$adapters" ] && ok "adapter(s): $adapters" || { bad "no adapter"; fail=1; }
fi
if systemctl is-active --quiet bluetooth; then ok "bluetooth.service active"
else bad "bluetooth.service not active (sudo systemctl enable --now bluetooth)"; fail=1; fi
if command -v bluetoothctl >/dev/null; then
    powered=$(timeout 5 bluetoothctl show 2>/dev/null | awk '/Powered:/{print $2}')
    [ "$powered" = "yes" ] && ok "adapter powered" || { bad "adapter not powered (bluetoothctl power on)"; fail=1; }
else bad "bluetoothctl missing (sudo apt install -y bluez)"; fail=1; fi

say "[3/6] python dependencies"
for m in bleak thermopro_ble; do
    if "$PY" -c "import $m" 2>/dev/null; then ok "$m present"
    else
        bad "$m missing"
        if [ "$MODE" = check ]; then fail=1
        else
            say "      installing $m"
            # shellcheck disable=SC2086
            "$PY" -m pip install --quiet $PIP_TARGET_FLAG "${m//_/-}" \
              || { bad "pip install ${m//_/-} failed"; fail=1; }
        fi
    fi
done

[ "$fail" = 0 ] || { say; say "[!] fix the above first; nothing was installed"; exit 1; }
[ "$MODE" = check ] && { say; say "[+] checks pass. Re-run without --check to probe and install."; exit 0; }

say "[4/6] what the sensor actually says"
say "      The sensor has no display. Compare the decoded values against"
say "      the vendor phone app showing it -- the app is the reference,"
say "      not either decoder."
say
"$PY" "$REPO/scripts/ble_probe_thermopro.py" --seconds "${PROBE_SECONDS:-45}" || true
say

if [ "$MODE" = ask ]; then
    read -r -p "Did the decoded values match the app's reading? [y/N] " ans
    case "$ans" in [yY]*) ;; *) say "[-] stopping. Send the hex above and the layout gets re-derived."; exit 0 ;; esac
fi

say "[5/6] installing the service"
tmp=$(mktemp)
sed -e "s|^User=.*|User=$USER_NAME|" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=$REPO|" \
    -e "s|^ExecStart=.*|ExecStart=$PY src/ambient_logger_ble.py $LOG --interval $INTERVAL --scan-window $WINDOW$NAME_ARG|" \
    "$REPO/scripts/ambient-logger-ble.service" > "$tmp"
sudo install -m 0644 "$tmp" "$UNIT" && rm -f "$tmp"
sudo systemctl daemon-reload
sudo systemctl enable --now ambient-logger-ble

say "      waiting for the first rows (one every ${INTERVAL}s)"
sleep $(( INTERVAL + WINDOW + 5 ))
printf '      service: %s / %s\n' "$(systemctl is-active ambient-logger-ble)" \
                                  "$(systemctl is-enabled ambient-logger-ble)"
if [ -f "$LOG" ]; then
    before=$(wc -l < "$LOG"); sleep $(( INTERVAL + 5 )); after=$(wc -l < "$LOG")
    printf '      log: %s lines, +%s in %ss\n' "$after" "$((after-before))" "$((INTERVAL+5))"
    tail -2 "$LOG" | sed 's/^/      /'
    [ "$after" -gt "$before" ] || bad "not growing -- journalctl -u ambient-logger-ble -n 50"
else
    bad "$LOG does not exist -- journalctl -u ambient-logger-ble -n 50"
fi
say
say "[+] done. The log is $LOG; copy it into the campaign directory as"
say "    <campaign>/deep_aging/ambient_<date>.csv so build_data_analysis.py sees it."
say "    Only one *ambient*.csv per campaign directory: the fusion globs."
