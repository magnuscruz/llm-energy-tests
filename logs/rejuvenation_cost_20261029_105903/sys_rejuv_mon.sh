#!/bin/bash
echo "timestamp,cpu_temp_c,ambient_c,humidity_pct,freq_khz_max,freq_khz_pcore_max,mem_used_mb,page_cache_mb,runner_rss_kb"
while true; do
    ts=$(date +%s.%3N)
    ctemp=$(sensors 2>/dev/null | awk '/Package id 0:|Core 0:/ {gsub(/[+°C]/,"",$0); for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\.[0-9]+$/){print $i; exit}}')
    amb_line=$(tail -n 1 "/home/ubuntu/ambient_ble.csv" 2>/dev/null)
    amb_c=$(echo "$amb_line" | awk -F',' '{print $2}')
    hum_pct=$(echo "$amb_line" | awk -F',' '{print $3}')
    pmax=$(cat /sys/devices/system/cpu/cpu{0..11}/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
    max=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null | sort -n | tail -1)
    mem_used=$(free -m | awk '/Mem:/ {print $3}')
    cached=$(awk '/^Cached:/ {printf "%d", $2/1024}' /proc/meminfo)
    rpid=$(pgrep -f "ollama.*runner" | head -1)
    if [ -n "$rpid" ] && [ -r "/proc/$rpid/status" ]; then
        orss=$(awk '/^VmRSS:/ {print $2}' "/proc/$rpid/status")
    else
        orss=0
    fi
    echo "$ts,${ctemp:-0},${amb_c:-0},${hum_pct:-0},${max:-0},${pmax:-0},${mem_used:-0},${cached:-0},${orss:-0}"
    sleep 1
done
