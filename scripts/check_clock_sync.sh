#!/usr/bin/env bash
# Measure clock offset between this machine and the measurement node.
#
# The fusion pipeline joins streams by UNIX epoch (Section III-F). If the two
# machines disagree, merge_asof pairs an ambient reading with the wrong
# inference event and reports nothing wrong. A Raspberry Pi Zero has no RTC: it
# takes its time from NTP at boot and drifts freely if that fails.
#
# Run before every campaign, and after any reboot of either machine.
#
#   ./check_clock_sync.sh user@measurement-node
#
# Offsets under ~1 s are harmless: the ambient stream is sampled at 1 Hz and the
# inference events it joins to are seconds to minutes apart. Beyond a few
# seconds, investigate before collecting anything.

set -uo pipefail
REMOTE="${1:?usage: $0 user@host}"
SAMPLES="${2:-5}"

command -v ssh >/dev/null || { echo "ssh not found" >&2; exit 1; }

echo "local : $(uname -n)  $(date -Is)"
echo "remote: $REMOTE"
echo

# Round-trip method: bracket the remote reading between two local ones, so
# network latency is bounded rather than mistaken for clock offset.
total=0; n=0
for _ in $(seq "$SAMPLES"); do
  t0=$(date +%s.%N)
  remote=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$REMOTE" 'date +%s.%N' 2>/dev/null) || {
    echo "[!] cannot reach $REMOTE over ssh" >&2; exit 1; }
  t1=$(date +%s.%N)
  read -r offset rtt < <(awk -v a="$t0" -v b="$remote" -v c="$t1" \
      'BEGIN{ printf "%.3f %.3f", b-(a+c)/2, c-a }')
  printf "  offset %+8.3f s   (rtt %.3f s)\n" "$offset" "$rtt"
  total=$(awk -v s="$total" -v o="$offset" 'BEGIN{print s+o}'); n=$((n+1))
  sleep 1
done

mean=$(awk -v s="$total" -v n="$n" 'BEGIN{printf "%.3f", s/n}')
echo
printf "mean offset: %+s s\n" "$mean"
awk -v m="$mean" 'BEGIN{
  a = (m<0 ? -m : m)
  if (a < 1)      print "OK: under 1 s, well inside the fusion tolerance."
  else if (a < 5) print "MARGINAL: investigate NTP on both machines before collecting."
  else            print "FAIL: fusion would pair readings with the wrong events."
}'

echo
echo "time sources:"
printf "  local : "; timedatectl show -p NTPSynchronized --value 2>/dev/null || echo "unknown"
printf "  remote: "; ssh -o BatchMode=yes "$REMOTE" \
  'timedatectl show -p NTPSynchronized --value 2>/dev/null || echo unknown'
