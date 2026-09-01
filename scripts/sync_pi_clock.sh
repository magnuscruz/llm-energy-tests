#!/usr/bin/env bash
# Set the ambient logger Pi's clock from the measurement node, over the USB link.
#
# WHY THIS EXISTS
# A Raspberry Pi Zero has no real-time clock. It takes its time from NTP at
# boot; with only a point-to-point USB link to this node and no route to the
# internet, NTP never succeeds and the Pi believes it is 1970. Every ambient
# sample it writes then carries a nonsense epoch, and the fusion step
# (Section III-F) joins them to the wrong inference events without complaining.
#
# Run this before starting a campaign, and after any reboot of the Pi.
#
#   ./sync_pi_clock.sh [user@host]        default: magnuspi@192.168.7.2

set -uo pipefail
PI="${1:-magnuspi@192.168.7.2}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)

offset_to() {   # round-trip: bracket the remote clock between two local reads
  local t0 remote t1
  t0=$(date +%s.%N)
  remote=$(ssh "${SSH_OPTS[@]}" "$PI" 'date +%s.%N' 2>/dev/null) || return 1
  t1=$(date +%s.%N)
  awk -v a="$t0" -v b="$remote" -v c="$t1" 'BEGIN{printf "%.3f", b-(a+c)/2}'
}

echo "node: $(uname -n)  $(date -Is)"
echo "pi  : $PI"

if ! before=$(offset_to); then
  echo "[!] cannot reach $PI over ssh." >&2
  echo "    Check the USB cable is in the Pi's DATA port (the middle one," >&2
  echo "    not PWR IN), and that this node has an address on the link:" >&2
  echo "      sudo ip addr add 192.168.7.1/24 dev usb0 && sudo ip link set usb0 up" >&2
  exit 1
fi
printf "offset before: %+s s\n" "$before"

# Push this node's time. The node is the reference because it is the machine
# whose telemetry everything else is joined to.
ssh "${SSH_OPTS[@]}" "$PI" "sudo -n date -s @$(date +%s) >/dev/null 2>&1" || {
  echo "[!] could not set the clock; does $PI have passwordless sudo for date?" >&2
  echo "    On the Pi:  echo '$(echo "$PI" | cut -d@ -f1) ALL=(ALL) NOPASSWD: /bin/date' | sudo tee /etc/sudoers.d/setclock" >&2
  exit 1
}
sleep 1

after=$(offset_to) || { echo "[!] lost the link after setting the clock" >&2; exit 1; }
printf "offset after : %+s s\n" "$after"

awk -v a="$after" 'BEGIN{
  d = (a<0 ? -a : a)
  if (d < 1) { print "OK: within 1 s, inside the fusion tolerance."; exit 0 }
  print "WARNING: still off by more than a second; do not start a campaign."; exit 1
}'
