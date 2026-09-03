#!/usr/bin/env bash
# Fetch the ambient log from the Pi into a campaign directory, and check it
# actually covers the campaign.
#
# The ambient stream is written on a separate machine, so nothing guarantees it
# ran for the whole campaign: the Pi may have rebooted, the card may have filled,
# the sensor may have dropped off the bus. A file that arrives is not a file that
# covers the run, and a partial ambient series silently weakens every
# ambient-adjusted claim. This reports the coverage rather than assuming it.
#
#   ./collect_ambient.sh logs/2026-09-10_48h_100_throttling [user@pi] [remote-file]

set -uo pipefail
CAMPAIGN="${1:?usage: $0 <campaign-dir> [user@pi] [remote-file]}"
PI="${2:-magnuspi@192.168.7.2}"
REMOTE="${3:-/home/magnuspi/ambient.csv}"

DEST="$CAMPAIGN/deep_aging"
[ -d "$DEST" ] || { echo "[!] $DEST not found" >&2; exit 1; }

# A source with no user@host is taken as a local path, so a file that arrived by
# some other route -- a USB stick, an earlier copy -- goes through the same
# coverage check. The check is the point; how the bytes travelled is not.
if [[ "$PI" == *@* ]]; then
  echo "[+] fetching $PI:$REMOTE"
  scp -o BatchMode=yes -o ConnectTimeout=10 "$PI:$REMOTE" "$DEST/ambient.csv" || {
    echo "[!] copy failed. Check the link is up (ip addr show usb0) and that the" >&2
    echo "    key is authorized: ssh $PI 'echo ok'" >&2; exit 1; }
else
  echo "[+] using local file $PI"
  [ -f "$PI" ] || { echo "[!] $PI not found" >&2; exit 1; }
  cp "$PI" "$DEST/ambient.csv"
fi

python3 - "$DEST" <<'PYEOF'
import glob, os, sys, csv
dest = sys.argv[1]

def span(path, col=0):
    lo = hi = None; n = 0
    with open(path) as fh:
        r = csv.reader(fh); next(r, None)
        for row in r:
            if not row: continue
            try: t = int(float(row[col]))
            except ValueError: continue
            lo = t if lo is None else min(lo, t)
            hi = t if hi is None else max(hi, t)
            n += 1
    return lo, hi, n

alo, ahi, an = span(f"{dest}/ambient.csv")
print(f"    ambient: {an:,} samples, {(ahi-alo)/3600:.2f} h")

# Compare against every model's inference window: the ambient logger runs once
# for the whole campaign, so it must cover all of them, not just the first.
# Track the best as well as the worst. A single uncovered model means partial
# coverage -- the logger stopped early. Only when NO model overlaps is the file
# wrong or the clocks disagreed, and those need different responses: one is a
# caveat to report, the other invalidates the collection.
pcts = {}
for f in sorted(glob.glob(f"{dest}/*_inference.csv")):
    lo, hi, n = span(f)
    inside = max(0, min(hi, ahi) - max(lo, alo))
    pct = 100.0 * inside / (hi - lo) if hi > lo else 0.0
    pcts[os.path.basename(f).split("_48")[0]] = pct
    flag = "" if pct > 99 else ("  <-- GAP" if pct > 0 else "  <-- NOT COVERED")
    print(f"    {os.path.basename(f).split('_48')[0]:<18} covered {pct:5.1f}%{flag}")

worst, best = min(pcts.values()), max(pcts.values())
print()
if worst > 99:
    print("[+] ambient covers every model window")
elif best <= 0:
    sys.exit("[!] no overlap with ANY model -- wrong file, or the clocks disagree."
             "\n    Run scripts/sync_pi_clock.sh before the next campaign.")
else:
    uncovered = [m for m, p in pcts.items() if p <= 99]
    print(f"[!] PARTIAL coverage. Incomplete for: {', '.join(uncovered)}")
    print("    The logger did not run for the whole campaign. Ambient-adjusted")
    print("    claims must either say so or exclude the uncovered models.")
    sys.exit(2)
PYEOF
rc=$?

echo
echo "[+] wrote $DEST/ambient.csv"
[ $rc -eq 0 ] && cat <<'EOF'
    Next: cd into that directory and run build_data_analysis.py, which now picks
    up *ambient*.csv automatically and adds ambient_c_mean / humidity_pct_mean.

    The Pi's card is small. Once this copy is verified, truncate the source:
      ssh <pi> 'sudo systemctl stop ambient-logger && : > ~/ambient.csv && sudo systemctl start ambient-logger'
EOF
exit $rc
