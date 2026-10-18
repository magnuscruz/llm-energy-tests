#!/usr/bin/env bash
# The pre-registered compute-bound boundary test: does the efficiency gain
# survive a workload whose cost is prefill rather than decode?
#
# Design is paper4-framework/preregistration/index.tex. One vision-language
# model serves both regimes and what varies is whether the request carries an
# image, so the weights, the engine and the node are identical across them.
# Pilot 2 cleared the manipulation: prefill:decode of 25.0 with an image
# against 0.14 without, a separation of 174x.
#
#   12 cells = 6 frequency caps x 2 regimes, in RANDOMISED order.
#
# Randomised because the main study's ladder was collected in cap order over
# four months, which left software version confounded with cap and is the
# criticism its reviewers raised first. Here the order is shuffled and
# recorded, and the whole matrix runs on one frozen stack in one sitting.
#
# WHAT THIS SCRIPT WATCHES THAT THE OLDER ONE DID NOT
#
# 1. Timeouts, per cell. A fixed request timeout interacts with the
#    independent variable: capping the clock makes inferences slower, so they
#    time out more often, and the events that survive at 50% are the fast
#    ones. That biases tokens-per-joule UPWARD exactly where the cap effect is
#    being measured. Pilot 2 lost one image in six at full speed, so this is
#    not hypothetical. Timeouts are counted per cell and a cell that exceeds
#    MAX_TIMEOUT_PCT is marked compromised in CAMPAIGN.md rather than quietly
#    averaged.
#
# 2. The configuration, per cell: kernel, Ollama version, model digest,
#    governor, EPP and the frequency actually sustained. Four of the seven
#    campaigns behind the main paper carry no such record, which that paper
#    now has to disclose.
#
# Usage:
#   ./scripts/run_ocr_campaign.sh --hours 4          # 12 cells, 48 h total
#   ./scripts/run_ocr_campaign.sh --hours 4 --dry-run
#   ./scripts/run_ocr_campaign.sh --hours 0.05 --cells 2   # smoke test
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MODEL=${OCR_MODEL:-granite3.2-vision:2b}
CORPUS=${OCR_CORPUS:-$PROJECT_ROOT/logs/ocr_corpus_compact}
BASE_FREQ_KHZ=3500000
# label:kHz. Written as kHz because the study's ladder includes 87.5% and
# 62.5%, which integer percentages cannot express.
CAPS=(100:3500000 87.5:3062500 75:2625000 62.5:2187500 50:1750000)
UNCAPPED_LABEL=R1
REGIMES=(image text)
HOURS=4
DRY=0
LIMIT_CELLS=0
# A request that has not returned by this point is abandoned. It must be well
# above the slowest cell's slowest page, or the timeout starts selecting.
OLLAMA_URL=${OLLAMA_URL:-http://localhost:11434}
REQ_TIMEOUT=${OCR_REQ_TIMEOUT:-1800}
MAX_TIMEOUT_PCT=${OCR_MAX_TIMEOUT_PCT:-5}
# Pilot 2 measured 3713 prompt tokens with an image, 95 without. Anything near
# the lower figure means the image was dropped, not that the page was sparse.
MIN_IMAGE_PREFILL=${OCR_MIN_IMAGE_PREFILL:-1000}
WARMUP_S=${OCR_WARMUP_S:-120}
# Room temperature and humidity, from the ThermoPro TP351S over BLE. Logged
# continuously by ambient-logger-ble.service into one file for the whole
# campaign; each cell takes its own slice, because build_data_analysis.py
# globs *ambient*.csv in the directory it is run from.
AMBIENT_LOG=${AMBIENT_LOG:-$HOME/ambient_ble.csv}
AMBIENT_MAX_AGE=${OCR_AMBIENT_MAX_AGE:-300}
NO_AMBIENT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --hours) HOURS=$2; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --cells) LIMIT_CELLS=$2; shift 2 ;;
    --no-ambient) NO_AMBIENT=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { echo "[!] $*" >&2; exit 1; }
say() { printf '%s\n' "$*"; }

# ---------------------------------------------------------------- preflight
command -v jq >/dev/null || die "jq missing"
command -v curl >/dev/null || die "curl missing"
command -v cpupower >/dev/null || die "cpupower missing"
[ -d "$CORPUS" ] || die "corpus not found: $CORPUS (run scripts/make_ocr_corpus.py)"
IMAGES=("$CORPUS"/*.png)
[ -e "${IMAGES[0]}" ] || die "no images in $CORPUS"
for img in "${IMAGES[@]}"; do
    [ -r "$img" ] && [ -s "$img" ] || die "unreadable or empty page: $img"
done
ollama list 2>/dev/null | grep -q "^${MODEL%%:*}" || die "model $MODEL not pulled"

PY=${OCR_PYTHON:-$PROJECT_ROOT/venv/bin/python3}
[ -x "$PY" ] || PY=$(command -v python3)

STAMP=$(date +%Y-%m-%d)
CAMPAIGN="$PROJECT_ROOT/logs/${STAMP}_ocr_boundary"
SAFE_MODEL=${MODEL//:/_}
HOURS_TAG=$(awk -v h="$HOURS" 'BEGIN{printf "%.2f", h}')
DURATION_S=$(awk -v h="$HOURS" 'BEGIN{printf "%d", h*3600}')

# ------------------------------------------------------------- cell ordering
# Shuffled once and written down, so the order is a recorded fact rather than
# whatever the loop happened to do.
declare -A CAP_KHZ
CELLS=()
for r in "${REGIMES[@]}"; do CELLS+=("$UNCAPPED_LABEL|$r"); done
for spec in "${CAPS[@]}"; do
  CAP_KHZ[${spec%%:*}]=${spec##*:}
  for r in "${REGIMES[@]}"; do CELLS+=("${spec%%:*}|$r"); done
done
mapfile -t CELLS < <(printf '%s\n' "${CELLS[@]}" | shuf)
[ "$LIMIT_CELLS" -gt 0 ] && CELLS=("${CELLS[@]:0:$LIMIT_CELLS}")

say "campaign : $CAMPAIGN"
say "model    : $MODEL"
say "corpus   : $CORPUS (${#IMAGES[@]} pages)"
say "cells    : ${#CELLS[@]} x ${HOURS}h  = $(awk -v n=${#CELLS[@]} -v h="$HOURS" 'BEGIN{printf "%.1f", n*h}')h"
say "order    : ${CELLS[*]//|/ }"
say "timeout  : ${REQ_TIMEOUT}s per request; a cell over ${MAX_TIMEOUT_PCT}% timeouts is flagged"
# Checked before the campaign starts, not discovered 48 h later: a dead
# sensor costs the whole ambient covariate, and the main study already has
# campaigns with no ambient record at all.
if [ "$NO_AMBIENT" = 0 ]; then
    [ -f "$AMBIENT_LOG" ] || die "no ambient log at $AMBIENT_LOG. Start it with scripts/setup_ambient_node.sh, or pass --no-ambient to run without room telemetry."
    ambient_last=$(tail -1 "$AMBIENT_LOG" | cut -d, -f1)
    case "$ambient_last" in ''|*[!0-9]*) die "ambient log has no readings yet: $AMBIENT_LOG" ;; esac
    ambient_age=$(( $(date +%s) - ambient_last ))
    [ "$ambient_age" -le "$AMBIENT_MAX_AGE" ] || die "ambient log is ${ambient_age}s stale (limit ${AMBIENT_MAX_AGE}s). Check: systemctl status ambient-logger-ble"
    say "ambient  : $AMBIENT_LOG, last reading ${ambient_age}s ago"
else
    say "ambient  : DISABLED (--no-ambient)"
fi

# --dry-run stops here: nothing is created and no credentials are read.
[ "$DRY" = 1 ] && { say "[dry-run] nothing executed"; exit 0; }

[ -f "$PROJECT_ROOT/.env" ] || die ".env not found (Tapo credentials; see .env.sample)"
set -a; . "$PROJECT_ROOT/.env"; set +a
mkdir -p "$CAMPAIGN"

# ------------------------------------------------------------------ helpers
apply_cap() {   # $1 = R1 | percent
    if [ "$1" = "$UNCAPPED_LABEL" ]; then
        sudo cpupower frequency-set -g performance >/dev/null
        sudo cpupower frequency-set -u $((BASE_FREQ_KHZ*2))kHz >/dev/null 2>&1 || true
    else
        sudo cpupower frequency-set -g powersave >/dev/null
        sudo cpupower frequency-set -u "${CAP_KHZ[$1]}kHz" >/dev/null
    fi
}

record_config() {   # $1 = cell dir, $2 = cap label
    {
        echo "cell=$2"
        echo "started=$(date -Is)"
        echo "kernel=$(uname -r)"
        echo "ollama_version=$(ollama --version 2>&1 | head -1)"
        echo "model=$MODEL"
        echo "model_digest=$(ollama list 2>/dev/null | awk -v m="$MODEL" '$1==m{print $2}')"
        echo "governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
        echo "epp=$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null || echo n/a)"
        echo "scaling_max_freq_pcore=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)"
        echo "scaling_max_freq_ecore=$(cat /sys/devices/system/cpu/cpu12/cpufreq/scaling_max_freq 2>/dev/null || echo n/a)"
        echo "corpus=$CORPUS"
        echo "req_timeout_s=$REQ_TIMEOUT"
    } > "$1/run_config.log"
}

# The two regimes, verbatim from scripts/pilot_ocr_regime.py so the campaign
# measures the manipulation the pilot validated and not a reworded cousin.
PROMPT_IMAGE="Transcribe all of the text in this image exactly as it appears. Output only the transcribed text."
PROMPT_TEXT="Write a detailed technical explanation, of at least eight hundred words, of how sustained inference load affects energy consumption and thermal behaviour on CPU-only edge hardware. Cover frequency scaling, memory bandwidth, and long-run throughput stability."

# ---------------------------------------------------------------- telemetry
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/tapo_monitor_temp.py" <<'EOF'
import asyncio, time, sys, os
from tapo import ApiClient

async def monitor():
    try:
        client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
        device = await client.p115(os.environ['TAPO_IP'])
        print('timestamp,power_w')
        sys.stdout.flush()
        while True:
            energy = await device.get_current_power()
            print(f'{int(time.time())},{energy.current_power}')
            sys.stdout.flush()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error in Tapo monitoring: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(monitor())
EOF
cat > "$WORK/freq_monitor_temp.sh" <<'EOF'
#!/bin/bash
echo "timestamp,freq_khz_max,freq_khz_mean,freq_khz_pcore_max"
while true; do
    ts=$(date +%s)
    freqs=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null)
    if [ -z "$freqs" ]; then
        echo "$ts,0,0,0"
    else
        max=$(printf "%s\n" $freqs | sort -n | tail -1)
        mean=$(printf "%s\n" $freqs | awk '{s+=$1} END {printf "%d", s/NR}')
        pmax=$(cat /sys/devices/system/cpu/cpu{0..11}/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
        echo "$ts,$max,$mean,${pmax:-0}"
    fi
    sleep 1
done
EOF
chmod +x "$WORK/freq_monitor_temp.sh"

# --------------------------------------------------------------- one request
# Writes one row and echoes "ok", "timeout" or "fatal". The payload goes to a file
# because a base64 page is ~80 kB and will not fit on a command line.
one_request() {   # $1 = regime, $2 = image path (may be empty), $3 = log file
    local regime=$1 img=$2 log=$3
    local cpu_temp ram_used cur_freq t0 t1
    cpu_temp=$(sensors 2>/dev/null | awk '/Core 0/ {print $3}' | tr -d '+°C')
    ram_used=$(free -m | awk '/Mem:/ {print $3}')
    cur_freq=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 0)

    if [ "$regime" = image ]; then
        # If base64 fails the request would still go out, just without an
        # image -- and the row would be recorded as image regime while
        # carrying no image. That is the manipulation silently collapsing,
        # which is the one failure this design cannot absorb. So it is fatal.
        # one_request runs inside $( ), so die here would kill only the
        # subshell and the campaign would carry on. The reason goes to a flag
        # file that the caller checks.
        local b64
        if ! b64=$(base64 -w0 "$img" 2>/dev/null) || [ -z "$b64" ]; then
            echo "cannot encode page $img" > "$WORK/fatal"
            echo fatal; return
        fi
        jq -n --arg m "$MODEL" --arg p "$PROMPT_IMAGE" --arg b "$b64" \
           '{model:$m, prompt:$p, stream:false, images:[$b]}' > "$WORK/payload.json"
    else
        jq -n --arg m "$MODEL" --arg p "$PROMPT_TEXT" \
           '{model:$m, prompt:$p, stream:false}' > "$WORK/payload.json"
    fi

    t0=$(date +%s)
    if ! curl -s --max-time "$REQ_TIMEOUT" "$OLLAMA_URL"/api/generate \
              -d @"$WORK/payload.json" > "$WORK/resp.json" 2>/dev/null \
       || ! jq -e '.eval_count' "$WORK/resp.json" >/dev/null 2>&1; then
        # A row is still written. Dropping the slow events is precisely the
        # bias this campaign has to avoid: they cluster at the low caps.
        t1=$(date +%s)
        echo "$t0,$MODEL,$regime,$(basename "${img:-none}"),$cpu_temp,$ram_used,$cur_freq,0,0,0,0,0,0,$((t1-t0)),1" >> "$log"
        echo timeout; return
    fi
    t1=$(date +%s)

    local pf_tok pf_ns de_tok de_ns
    pf_tok=$(jq -r '.prompt_eval_count // 0' "$WORK/resp.json")
    pf_ns=$(jq -r '.prompt_eval_duration // 1' "$WORK/resp.json")
    de_tok=$(jq -r '.eval_count // 0' "$WORK/resp.json")
    de_ns=$(jq -r '.eval_duration // 1' "$WORK/resp.json")
    [ "$pf_ns" -gt 0 ] 2>/dev/null || pf_ns=1
    [ "$de_ns" -gt 0 ] 2>/dev/null || de_ns=1

    local pf_tps de_tps pf_s de_s
    pf_tps=$(echo "scale=2; ($pf_tok * 1000000000) / $pf_ns" | bc)
    de_tps=$(echo "scale=2; ($de_tok * 1000000000) / $de_ns" | bc)
    pf_s=$(echo "scale=6; $pf_ns / 1000000000" | bc)
    de_s=$(echo "scale=6; $de_ns / 1000000000" | bc)

    echo "$t0,$MODEL,$regime,$(basename "${img:-none}"),$cpu_temp,$ram_used,$cur_freq,$pf_tps,$de_tps,$pf_s,$de_s,$pf_tok,$de_tok,$((t1-t0)),0" >> "$log"
    echo ok
}

# ------------------------------------------------------------------ one cell
run_cell() {   # $1 = index, $2 = cap label, $3 = regime
    local idx=$1 cap=$2 regime=$3
    local name; name=$(printf 'cell_%02d_%s_%s' "$idx" "$cap" "$regime")
    local dir="$CAMPAIGN/$name/deep_aging"
    mkdir -p "$dir"

    say ""
    say "=========================================================="
    say "[$idx/${#CELLS[@]}] cap=$cap regime=$regime  ->  $name"
    say "=========================================================="

    apply_cap "$cap"
    sleep 2

    # Verify on both core types. A cap that did not take is the failure that
    # silently invalidated two campaigns of the main study; here it aborts.
    local want_khz pmax emax
    pmax=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq)
    emax=$(cat /sys/devices/system/cpu/cpu12/cpufreq/scaling_max_freq 2>/dev/null || echo "$pmax")
    if [ "$cap" = "$UNCAPPED_LABEL" ]; then
        # The uncapped cell must be checked too. A leftover ceiling from the
        # previous cell would turn R1 into a sixth capped point while the
        # filename still said uncapped, which is how two campaigns of the main
        # study were lost.
        # Compared against the hardware ceiling the kernel reports, not a
        # number written here: 3500000 is the E-core turbo, so a 100% cap left
        # on the E-cores is indistinguishable from uncapped if you test it
        # against a constant.
        local phw ehw
        phw=$(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq)
        ehw=$(cat /sys/devices/system/cpu/cpu12/cpufreq/cpuinfo_max_freq 2>/dev/null || echo "$phw")
        if [ "$pmax" -lt "$phw" ] || [ "$emax" -lt "$ehw" ]; then
            die "uncapped cell still carries a ceiling (P=${pmax}/${phw} E=${emax}/${ehw}); aborting"
        fi
    else
        want_khz=${CAP_KHZ[$cap]}
        if [ "$pmax" -gt $(( want_khz + 50000 )) ] || [ "$emax" -gt $(( want_khz + 50000 )) ]; then
            die "cap $cap% did not take (wanted ${want_khz}, P=${pmax} E=${emax}); aborting"
        fi
    fi
    record_config "$CAMPAIGN/$name" "$cap"

    local log="$dir/${SAFE_MODEL}_${HOURS_TAG}h_inference.csv"
    echo "timestamp,model,regime,page,cpu_temp,ram_used_mb,scaling_cur_freq,prefill_tps,decode_tps,prefill_dur_s,decode_dur_s,prefill_tokens,decode_tokens,wall_s,timed_out" > "$log"

    # Short warm-up, discarded. The model stays resident across cells, so the
    # 600 s residency ramp of the main study is paid once, not twelve times;
    # this only re-stabilises the clock after the cap change.
    # The image regime is defined by prefill mass: the pilot saw 3713 prompt
    # tokens with an image against 95 without. If the image stops reaching the
    # encoder the run still completes and still looks like a campaign, so the
    # first warm-up response is checked against a floor before four hours are
    # spent on it.
    if [ "$regime" = image ]; then
        one_request image "${IMAGES[0]}" /dev/null >/dev/null
        local pf; pf=$(jq -r '.prompt_eval_count // 0' "$WORK/resp.json" 2>/dev/null || echo 0)
        [ "$pf" -ge "$MIN_IMAGE_PREFILL" ] 2>/dev/null \
            || die "image regime not engaged: prefill $pf tokens, floor $MIN_IMAGE_PREFILL (pilot saw 3713). The image is not reaching the encoder."
        say "    image regime confirmed: $pf prefill tokens"
    fi

    say "    warm-up ${WARMUP_S}s (discarded)"
    local warm_end=$(( $(date +%s) + WARMUP_S )) i=0
    while [ "$(date +%s)" -lt "$warm_end" ]; do
        one_request "$regime" "${IMAGES[$(( i % ${#IMAGES[@]} ))]}" /dev/null >/dev/null
        i=$(( i + 1 ))
    done

    local t_start; t_start=$(date +%s)
    $PY "$WORK/tapo_monitor_temp.py" > "$dir/${SAFE_MODEL}_${HOURS_TAG}h_physical.csv" \
                                     2> "$dir/${SAFE_MODEL}_${HOURS_TAG}h_physical.err" &
    local tapo_pid=$!
    "$WORK/freq_monitor_temp.sh" > "$dir/${SAFE_MODEL}_${HOURS_TAG}h_freq.csv" 2>/dev/null &
    local freq_pid=$!

    local end=$(( $(date +%s) + DURATION_S )) n=0 nto=0 r
    i=0
    while [ "$(date +%s)" -lt "$end" ]; do
        r=$(one_request "$regime" "${IMAGES[$(( i % ${#IMAGES[@]} ))]}" "$log")
        if [ "$r" = fatal ]; then
            kill "$tapo_pid" "$freq_pid" 2>/dev/null || true
            die "$(cat "$WORK/fatal")"
        fi
        n=$(( n + 1 )); i=$(( i + 1 ))
        [ "$r" = timeout ] && nto=$(( nto + 1 ))
    done

    kill "$tapo_pid" "$freq_pid" 2>/dev/null || true
    wait "$tapo_pid" "$freq_pid" 2>/dev/null || true

    # Slice the room telemetry to this cell's window. Copied rather than
    # symlinked so the cell stays readable if the logger rotates or the node
    # is reimaged, and so each cell carries its own ambient record.
    local amb_rows=0
    if [ "$NO_AMBIENT" = 0 ] && [ -f "$AMBIENT_LOG" ]; then
        local t_end; t_end=$(date +%s)
        awk -F, -v a="$t_start" -v b="$t_end" \
            'NR==1 {print; next} $1+0>=a && $1+0<=b {print}' \
            "$AMBIENT_LOG" > "$dir/ambient_ble.csv"
        amb_rows=$(( $(wc -l < "$dir/ambient_ble.csv") - 1 ))
        say "    ambient: $amb_rows readings over $(( (t_end-t_start)/60 )) min"
        [ "$amb_rows" -gt 0 ] || say "    [!] ambient gap: the sensor logged nothing during this cell"
    fi

    local pct=0
    [ "$n" -gt 0 ] && pct=$(awk -v a="$nto" -v b="$n" 'BEGIN{printf "%.1f", 100*a/b}')
    local flag=""
    awk -v p="$pct" -v m="$MAX_TIMEOUT_PCT" 'BEGIN{exit !(p>m)}' && flag=" **COMPROMISED**"
    say "    $n events, $nto timed out (${pct}%)$flag"
    printf '| %s | %s | %s | %d | %d | %s%% |%s\n' \
        "$idx" "$cap" "$regime" "$n" "$nto" "$pct" "$flag" >> "$CAMPAIGN/_cells.md"
    {   echo "events=$n"; echo "timeouts=$nto"; echo "timeout_pct=$pct"
        echo "ambient_rows=$amb_rows"
        echo "finished=$(date -Is)"
    } >> "$CAMPAIGN/$name/run_config.log"
}

# ------------------------------------------------------------------- execute
: > "$CAMPAIGN/_cells.md"
idx=0
for cell in "${CELLS[@]}"; do
    idx=$(( idx + 1 ))
    run_cell "$idx" "${cell%%|*}" "${cell##*|}"
done

# Leave the node unthrottled.
sudo cpupower frequency-set -g performance >/dev/null 2>&1 || true
sudo cpupower frequency-set -u $((BASE_FREQ_KHZ*2))kHz >/dev/null 2>&1 || true

{
    echo "# OCR boundary campaign — $STAMP"
    echo
    echo "Pre-registration: \`paper4-framework/preregistration/index.tex\`."
    echo "Manipulation validated by pilot 2 (\`logs/pilot_ocr2.out\`): prefill:decode"
    echo "25.0 with an image against 0.14 without, a separation of 174x."
    echo
    echo "- model: \`$MODEL\`"
    echo "- corpus: \`$CORPUS\` (${#IMAGES[@]} pages, round-robin)"
    echo "- cells: ${#CELLS[@]} = caps x regimes, **randomised**, ${HOURS} h each"
    echo "- order as executed: \`${CELLS[*]//|/ }\`"
    echo "- request timeout: ${REQ_TIMEOUT} s"
    echo "- ambient: ThermoPro TP351S over BLE, sliced per cell into"
    echo "  \`<cell>/deep_aging/ambient_ble.csv\` (\`ambient_rows\` in each"
    echo "  \`run_config.log\`)"
    echo
    echo "## Timeouts per cell"
    echo
    echo "A timeout is not a missing event: it is an event too slow to finish,"
    echo "and the low caps produce more of them. Dropping them would bias"
    echo "tokens-per-joule upward exactly where the cap effect is measured, so"
    echo "every timeout is written to the inference CSV with \`timed_out=1\` and"
    echo "counted here. A cell above ${MAX_TIMEOUT_PCT}% is marked and must not be"
    echo "read as a clean measurement."
    echo
    echo "| # | cap | regime | events | timeouts | rate |"
    echo "|---|-----|--------|--------|----------|------|"
    cat "$CAMPAIGN/_cells.md"
    echo
    echo "Per-cell \`run_config.log\` carries kernel, Ollama version, model digest,"
    echo "governor, EPP and the verified ceiling — the record four of the seven"
    echo "campaigns in the main study do not have."
} > "$CAMPAIGN/CAMPAIGN.md"
rm -f "$CAMPAIGN/_cells.md"

say ""
say "done. $CAMPAIGN/CAMPAIGN.md"
