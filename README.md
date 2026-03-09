# Workflow

## Energy LOG

```bash
sudo powerstat -R 1 3600 > energy_log.txt &
```

## Stress lopping

```bash
screen -d -m bash -c 'while true; do curl -s -X POST http://localhost:11434/api/generate -d "{\"model\": \"llama3:8b\", \"prompt\": \"stresstest\", \"stream\": false}" > /dev/null; done'
```

## Monitoring

```bash
watch -n 1 "free -h && nvidia-smi --query-gpu=power.draw,memory.used --format=csv"
```

## Create a CSV File results

```bash
grep -E '^[0-9]' energy_log.txt | awk '{print $1","$11}' > final_report.csv
```

## The Automation Script (scripts/run_test.sh)

Create a script that starts the power monitoring, runs the LLM stress test, and formats the output for Git.

##  Git Integration & "Auto-Commit"

To avoid losing data during long aging tests, you can create a small "sync" script or add this to the end of your main script:

```bash
# Add this to the end of run_test.sh
git add logs/*.csv
git commit -m "Results for $MODEL test at $TIMESTAMP"
git push origin main
```