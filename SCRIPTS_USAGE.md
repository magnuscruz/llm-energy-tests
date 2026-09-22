# LLM Energy Tests - Scripts Usage Guide

Comprehensive documentation for all automation scripts in the `scripts/` directory.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation & Setup](#installation--setup)
3. [Scripts Overview](#scripts-overview)
4. [Detailed Usage](#detailed-usage)
   - [run_benchmark_pair.sh](#run_benchmark_pairsh)
   - [run_dashboard.sh](#run_dashboardsh)
   - [deploy_hf_spaces.sh](#deploy_hf_spacessh)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **CPU**: Multi-core processor (8+ cores recommended)
- **RAM**: 16GB+ minimum
- **GPU**: Optional (NVIDIA GPU with CUDA support for acceleration)
- **Root Access**: Required for thermal throttling and power monitoring

### Required Software
```bash
# Core utilities
sudo apt-get update
sudo apt-get install -y jq bc curl lm-sensors cpupower

# Python environment
python3 --version  # 3.8+
pip3 install --upgrade pip

# Ollama (LLM inference engine)
# Download from https://ollama.ai
ollama --version
```

### Optional Dependencies
- **Tapo P115 Smart Plug**: For physical power measurement via `tapo` Python library
- **GPU Support**: NVIDIA GPU with CUDA for faster inference

---

## Installation & Setup

### 1. Clone Repository
```bash
cd ~
git clone https://github.com/magnuscruz/llm-energy-tests.git
cd llm-energy-tests
```

### 2. Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r src/requirements.txt

# Install Tapo library (if using Tapo P115 plug)
pip install tapo
```

### 3. Configure Tapo Smart Plug (Optional)
Edit scripts and set these environment variables:
```bash
export TAPO_USER="your-email@example.com"
export TAPO_PASS="your-password"
export TAPO_IP="192.168.0.100"  # Your Tapo plug IP address
```

### 4. Start Ollama Service
```bash
# Start Ollama (background)
ollama serve &

# Or use systemd
sudo systemctl start ollama

# Verify it's running
curl http://localhost:11434/api/tags
```

### 5. Pre-download Models (Optional but Recommended)
```bash
ollama pull qwen2.5:0.5b
ollama pull gemma2:2b
ollama pull phi3:mini
ollama pull llama3.1:8b
ollama pull mistral:7b
ollama pull deepseek-v2:lite
```

---

## Scripts Overview

| Script | Purpose | Requires Root | Duration |
|--------|---------|---------------|----------|
| `run_benchmark_pair.sh` | Pairwise dense vs MoE model comparison | ✅ Yes | Variable |
| `run_dashboard.sh` | Launch Streamlit visualization dashboard | ❌ No | N/A |
| `deploy_hf_spaces.sh` | Deploy dashboard to Hugging Face Spaces | ❌ No | N/A |
| `run_clear.sh` | Clean up logs and temporary files | ❌ No | N/A |
| `run_tests.sh` | Quick validation test suite | ❌ No | 5-10 min |

---

## Detailed Usage

### run_benchmark_pair.sh

**Purpose**: Pairwise comparison of models under identical conditions (for statistical analysis).

**Usage**:
```bash
sudo ./scripts/run_benchmark_pair.sh <duration_seconds> [--throttle <percentage>]
```

**Parameters**:
Same as `run_benchmark_pair.sh` but focuses on specific model pairs:
- qwen2.5:0.5b (smallest, most efficient)
- phi3:mini (small, efficient)
- llama3.1:8b (dense, reference baseline)
- deepseek-v2:lite (MoE, efficient at scale)

**Examples**:

```bash
# 12-hour pairwise comparison with 75% throttling
sudo nohup ./scripts/run_benchmark_pair.sh 43200 --throttle 75 > pair_comparison.log 2>&1 &

# 48-hour aging test for paper publication
sudo nohup ./scripts/run_benchmark_pair.sh 172800 > aging_paper_48h.log 2>&1 &
```

**Differences from run_benchmark_pair.sh**:
- Logs in format: `model_name_<duration>h_inference.csv`
- Phase-aware metrics: `prefill_tps`, `decode_tps` (separate throughput measurements)
- Includes timestamp in Unix epoch format for precise synchronization
- Better for comparative statistical analysis

**Output Format** (updated):
```csv
timestamp,model,cpu_temp,ram_used_mb,prefill_tps,decode_tps
1715425200,llama3.1:8b,65.5,8192,45.23,52.10
1715425201,llama3.1:8b,65.8,8192,46.15,51.95
```

---

### run_dashboard.sh

**Purpose**: Launch interactive Streamlit dashboard for visualizing benchmark results.

**Usage**:
```bash
./scripts/run_dashboard.sh [optional_date_filter]
```

**Parameters**:
- `[optional_date_filter]`: Filter logs by date (optional)
  - Format: YYYYMMDD (e.g., 20260511)

**Examples**:

```bash
# Launch dashboard without filter
./scripts/run_dashboard.sh

# Launch dashboard showing only May 5, 2026 data
./scripts/run_dashboard.sh 20260505

# Launch with custom port
streamlit run ./src/build_dashboard.py --server.port 9000
```

**Dashboard Features**:
1. **Phase-Aware Inference Pipeline**
   - Decode Throughput (TPS) over time
   - Memory usage trends
   
2. **Thermal & Physical Hardware Constraints**
   - CPU temperature accumulation
   - Physical power draw (from Tapo P115)
   - System resource utilization

3. **Experiment Date Selection**
   - Multi-select up to 2 dates for comparison
   - Export options (PDF, SVG, EPS, PNG)
   - Configurable DPI for publication-quality figures

4. **Raw Data Preview**
   - First 100 rows of merged telemetry data
   - Expandable raw CSV viewer

**Access**:
- Local: http://localhost:8501
- Remote: http://<machine-ip>:8501
- SSH Tunnel: `ssh -L 8501:localhost:8501 user@remote-machine`

**Troubleshooting Dashboard**:
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/

# Run with verbose logging
streamlit run ./src/build_dashboard.py --logger.level=debug

# Kill existing streamlit process
pkill -f streamlit
```

---

### deploy_hf_spaces.sh

**Purpose**: Automate deployment of dashboard to Hugging Face Spaces with GitHub integration.

**Usage**:
```bash
./scripts/deploy_hf_spaces.sh
```

**Prerequisites**:
- GitHub account with repository access
- Hugging Face account (free tier sufficient)
- Git configured locally:
  ```bash
  git config --global user.name "Your Name"
  git config --global user.email "your.email@example.com"
  ```

**Interactive Steps**:

1. **GitHub Check**
   - Verifies Git configuration
   - Prompts to commit uncommitted changes
   - Pushes to GitHub

2. **File Creation**
   - Creates `app.py` (HF Spaces entry point)
   - Updates `.gitignore`
   - Generates `app_template.py`

3. **Manual HF Spaces Setup** (script provides instructions):
   ```bash
   # After script completes, follow these steps:
   1. Visit https://huggingface.co/new-space
   2. Create Space:
      - Name: llm-energy-tests-dashboard
      - SDK: Streamlit
      - License: MIT/Apache 2.0
   3. Enable GitHub auto-deploy
   4. Dashboard auto-updates on git push
   ```

**Example**:
```bash
cd ~/git/llm-energy-tests
./scripts/deploy_hf_spaces.sh

# Follow interactive prompts:
# - Commit changes? (y/n)
# - Enter commit message
# - Wait for GitHub push
# - Follow HF Spaces setup instructions
```

**Final Dashboard URL**:
```
https://huggingface.co/spaces/magnuscruz/llm-energy-tests
```

**Auto-Deployment After Setup**:
```bash
# Any git push to 'main' automatically redeploys
git add .
git commit -m "Update dashboard"
git push origin main  # <- Triggers auto-deploy

# Monitor build at: https://huggingface.co/spaces/magnuscruz/llm-energy-tests
```

---

## Common Patterns

### Running Multiple Benchmarks in Sequence

```bash
#!/bin/bash
# Run multiple benchmark configs without manual intervention

# 24-hour baseline (no throttling)
sudo ./scripts/run_benchmark_pair.sh 86400

# 24-hour with 50% throttling
sudo ./scripts/run_benchmark_pair.sh 86400 --throttle 50

# 24-hour with 75% thermal stress
sudo ./scripts/run_benchmark_pair.sh 86400 --throttle 75

echo "All benchmarks completed!"
```

### Running in Background with Logs

```bash
# Start benchmark and save to log
sudo nohup ./scripts/run_benchmark_pair.sh 172800 --throttle 62.5 \
    > logs/benchmark_run_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Get the process ID
PID=$!
echo "Benchmark running as PID $PID"

# Monitor logs in real-time
tail -f logs/benchmark_run_*.log

# Check if still running
ps -p $PID
```

### Comparing Before & After Optimization

```bash
# Before optimization
sudo ./scripts/run_benchmark_pair.sh 43200 --throttle 75
# Saves to logs/YYYY-MM-DD/deep_aging/*

# [Make your optimization changes]

# After optimization  
sudo ./scripts/run_benchmark_pair.sh 43200 --throttle 75
# Saves to logs/YYYY-MM-DD/deep_aging/*

# View both in dashboard
./scripts/run_dashboard.sh
# Multi-select both YYYY-MM-DD dates for comparison
```

### Automated Daily Benchmarking (Cron)

```bash
# Add to crontab: crontab -e
0 2 * * * /home/ubuntu/git/llm-energy-tests/scripts/run_benchmark_pair.sh 86400 --throttle 50 >> /var/log/llm_benchmark.log 2>&1

# Run overnight benchmarks (2 AM daily)
# Monitor with: tail -f /var/log/llm_benchmark.log
```

---

## Troubleshooting

### Issue: "Permission Denied" on Benchmark Scripts

**Solution**:
```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run with sudo
sudo ./scripts/run_benchmark_pair.sh 3600
```

### Issue: "Ollama Connection Refused"

**Solution**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve &

# Or use systemd
sudo systemctl start ollama
sudo systemctl status ollama
```

### Issue: "ModuleNotFoundError: No module named 'streamlit'"

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r src/requirements.txt

# Then run dashboard
./scripts/run_dashboard.sh
```

### Issue: Benchmark Runs Too Slow / High Latency

**Solution**:
```bash
# Pre-download models before benchmarking
ollama pull llama3.1:8b
ollama pull mistral:7b

# Disable throttling for baseline performance
sudo ./scripts/run_benchmark_pair.sh 3600  # No --throttle flag

# Check system resources
free -h
top -b -n 1 | head -20
nvidia-smi  # If using GPU
```

### Issue: "No Log Directories Found in Base Path"

**Solution**:
```bash
# Dashboard looks for logs at: ~/git/llm-energy-tests/logs/
# Verify the path exists
ls -la ~/git/llm-energy-tests/logs/

# If missing, create it and run a quick benchmark
mkdir -p ~/git/llm-energy-tests/logs
sudo ./scripts/run_benchmark_pair.sh 600
```

### Issue: Tapo P115 Power Monitor Not Working

**Solution**:
```bash
# Verify Tapo library is installed
pip install tapo

# Test Tapo connection manually
python3 << 'EOF'
import asyncio
from tapo import ApiClient
import os

async def test():
    client = ApiClient(os.environ['TAPO_USER'], os.environ['TAPO_PASS'])
    device = await client.p115(os.environ['TAPO_IP'])
    energy = await device.get_current_power()
    print(f"Current Power: {energy.current_power}W")

asyncio.run(test())
EOF

# If connection fails:
# 1. Verify TAPO_USER, TAPO_PASS, TAPO_IP are correct
# 2. Check Tapo plug is on same network
# 3. Verify firewall allows connection
```

### Issue: Dashboard Plots Not Loading

**Solution**:
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/

# Verify data files exist
ls -la logs/YYYY-MM-DD/deep_aging/

# Check data format
head logs/YYYY-MM-DD/deep_aging/*_inference.csv

# Run dashboard with debug logging
streamlit run ./src/build_dashboard.py --logger.level=debug
```

### Issue: Git Push Failed During Deploy

**Solution**:
```bash
# Check git status
git status

# Verify remote is configured
git remote -v

# Set correct remote if missing
git remote add origin https://github.com/magnuscruz/llm-energy-tests.git

# Try push again
git push origin main

# If still fails, check credentials
git config --global user.name
git config --global user.email
```

---

## Performance Tips

### For Faster Benchmarks
```bash
# Use smaller models for quick tests
MODELS=("phi3:mini" "qwen2.5:0.5b")

# Run shorter duration (300s = 5 minutes)
sudo ./scripts/run_benchmark_pair.sh 300
```

### For Publication-Quality Results
```bash
# Run long benchmarks with consistent conditions
# 1. No throttling baseline
sudo ./scripts/run_benchmark_pair.sh 172800  # 48 hours

# 2. Thermal stress case
sudo ./scripts/run_benchmark_pair.sh 172800 --throttle 75  # 48 hours

# 3. Compare in dashboard
./scripts/run_dashboard.sh

# 4. Export figures as PDF/SVG (300 DPI)
# Use dashboard export options
```

### Resource Monitoring During Benchmarks
```bash
# In separate terminal, monitor system
watch -n 1 "free -h && top -b -n 1 | head -10 && nvidia-smi"

# Or log to file
(while true; do echo "=== $(date) ==="; free -h; top -bn1 | head -5; sleep 10; done) > system_monitor.log &
```

---

## Contact & Support

For issues or questions:
- **GitHub Issues**: https://github.com/magnuscruz/llm-energy-tests/issues
- **Documentation**: See [DEPLOY_HF_SPACES.md](DEPLOY_HF_SPACES.md) for deployment troubleshooting
- **Dashboard Guide**: See [build_dashboard.py](src/build_dashboard.py) for visualization features

---

**Last Updated**: May 11, 2026
