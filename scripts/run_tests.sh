#!/bin/bash
# Usage: ./run_test.sh <duration_in_seconds> <model_name>~
# Example: ./run_test.sh 300 llama3:8b

DURATION=$1
MODEL=$2
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/energy_${MODEL}_${TIMESTAMP}.txt"
CSV_FILE="logs/energy_${MODEL}_${TIMESTAMP}.csv"

echo "Starting energy test for $MODEL ($DURATION seconds)..."

# 1. Start powerstat in background
sudo powerstat -R 1 "$DURATION" > "$LOG_FILE" &
POWER_PID=$!

# 2. Run LLM stress loop
END_TIME=$((SECONDS + DURATION))
while [ $SECONDS -lt $END_TIME ]; do
    curl -s -X POST http://localhost:11434/api/generate -d "{
        \"model\": \"$MODEL\",
        \"prompt\": \"Explain quantum computing in detail.\",
        \"stream\": false
    }" > /dev/null
done

wait $POWER_PID

# 3. Format text log to CSV for easier Git/Excel analysis
grep -E '^[0-9]' "$LOG_FILE" | awk '{print $1","$11}' > "$CSV_FILE"
echo "Test complete. Results saved to $CSV_FILE"
