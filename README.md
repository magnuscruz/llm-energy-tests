---
title: LLM Energy Tests Dashboard
emoji: 🌡️
colorFrom: yellow
colorTo: red
sdk: streamlit
sdk_version: "1.39.0"
python_version: "3.10"
app_file: app.py
pinned: false
---

# LLM Energy Tests: Software Aging & Carbon-Aware Resilience in Edge-Deployed LLMs

Research benchmark framework investigating long-term sustainability of Large Language Models deployed on edge hardware under continuous workloads.

**Paper**: "Software Aging and Carbon-Aware Resilience in Edge-Deployed LLMs" - DEI, UC, Portugal

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Experimental Methodology](#experimental-methodology)
3. [Key Findings](#key-findings)
4. [Scripts & Workflows](#scripts--workflows)
5. [Project Structure](#project-structure)
6. [Deployment](#deployment)

---

## Quick Start

### Prerequisites
```bash
# System utilities
sudo apt-get install -y jq bc curl lm-sensors cpupower

# Python 3.8+
python3 --version

# Ollama (LLM inference engine)
# Download from https://ollama.ai
ollama serve &  # Start in background
```

### Installation
```bash
git clone https://github.com/magnuscruz/llm-energy-tests.git
cd llm-energy-tests

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt

# Pre-download models (optional but recommended)
ollama pull qwen2.5:0.5b
ollama pull llama3.1:8b
ollama pull phi3:mini
ollama pull deepseek-v2:lite
```

### Run Benchmark
```bash
# 1 hour per model, no throttling
sudo ./scripts/run_benchmark.sh 3600

# 48-hour aging test with thermal constraints
sudo nohup ./scripts/run_benchmark.sh 172800 --throttle 75 > benchmark.log 2>&1 &

# View results in dashboard
./scripts/run_dashboard.sh
```

For detailed usage, see [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md).

---

## Experimental Methodology

### Hardware Configuration
- **CPU**: Intel Core i5-13500
- **RAM**: 64 GB
- **Power**: ~160W max draw
- **OS**: Ubuntu 24.04.4 LTS
- **Power Monitor**: Tapo P115 Smart Plug (1 Hz telemetry)

### Deep Aging 5-Phase Protocol

Our empirical framework executes a rigorous **5-phase "DEEP AGING" experimental roadmap**:

#### Phase 1: Automated Zero-State Rejuvenation
- Unload model from memory
- Restart inference service (Ollama)
- Clear Linux page cache and swap: `drop_caches`
- 1-hour thermal cooling bridge to guarantee ambient baseline

#### Phase 2: Architectural Hypothesis & Capping
- Pair Dense vs. MoE models for comparison
- Apply CPU frequency caps using `cpupower`:
  - **Unthrottled**: Full performance
  - **87.5%**: Severe thermal stress
  - **75%**, **62.5%**, **50%**: Progressive constraints
- Test hardware mitigation effectiveness

#### Phase 3: 48-Hour Phase-Aware Observation
- Subject models to continuous 48-hour workloads
- Extract **phase-aware metrics** every inference:
  - `ram_used_mb`: System memory utilization
  - `cpu_temp`: CPU temperature (°C)
  - `prefill_tps`: Tokens/sec during context processing
  - `decode_tps`: Tokens/sec during autoregressive generation
- Track progressive pipeline starvation and thermal accumulation

#### Phase 4: Carbon-Aware Eco-Efficiency Metric
- Poll physical power draw via Tapo P115 at **1 Hz**
- Map energy consumption to grid carbon intensity
- Calculate **Carbon-Aware Eco-Efficiency**:
  ```
  CE = Tokens Generated / (Wattage × CIgrid)
  ```
  where CIgrid = grid carbon intensity (gCO₂eq/kWh)

#### Phase 5: Statistical Quantification
- Apply 60-second moving average smoothing
- Mann-Kendall test for monotonic trends
- Sen's slope estimator for degradation rates
- Validate long-term sustainability patterns

### Models Evaluated

| Model | Parameters | Architecture | Role |
|-------|-----------|--------------|------|
| **Qwen2.5 0.5B** | 0.5B | Ultra-Light Dense | Efficiency Baseline |
| **Phi-3 Mini** | 3.8B | Packed Dense | Edge Reference |
| **Llama 3.1 8B** | 8B | Mid-Weight Dense | Standard Baseline |
| **DeepSeek-v2 Lite** | 15.7B (2.4B active) | Sparse MoE | Efficiency Optimized |

### Inference Prompt
All models tested with identical standardized prompt:
```
"Analyze the implications of software aging on distributed 
edge network reliability."
```

---

## Key Findings

### Dense Model Resilience: Active Memory Oscillation
- **Llama 3.1 8B** survives 48-hour continuous load through **OS-level memory sawtooth oscillation**
- RAM fluctuation pattern: ~20 MB periodic drops prevent cache starvation
- Decode throughput remains stable: **12.23 TPS** (only 1.62% degradation over 48h)
- **Thermal penalty**: Continuous redlining at **63°C**, 143-151W sustained power

### Sparse MoE Thermal Advantage
- **DeepSeek-v2 Lite** eliminates memory creep through Multi-Head Latent Attention (MLA)
- RAM variance: **56 MB total** (0.51% of footprint) - near-zero oscillation
- Decode throughput: **29.31 TPS** (1.38% degradation)
- **Thermal breathing**: Sparse activation creates power dips (129-144W), allowing passive cooling recovery to 42°C
- Peak prefill throughput: **>700 TPS** via efficient KV-cache compression

### Packed Model Failure: EOS Attention Corruption
- **Phi-3 Mini** suffers catastrophic thermal stress collapse
- Intensive compression forces unrelenting thermal load (peak **64°C**)
- **Critical degradation**: Autoregressive generation drops from 23.74 → 16.09 TPS
- Loss of EOS token processing capability triggers "infinite babbling loop"
- **Carbon waste**: 86.7% efficiency collapse under thermal stress

### Ultra-Lightweight Baseline: Safe Edge Operation
- **Qwen2.5 0.5B** maintains >100 TPS without thermal stress
- RAM footprint: **1.7-2.0 GB** (negligible bloat)
- CPU temps stable: **44-47°C** (no redlining)
- Proves catastrophic failures are architectural, not hardware-inherent

### Thermal Mitigation Futility
- Reboot-based rejuvenation **completely ineffective** as placebo constraint
- Physical thermodynamic limits dictate degradation, not OS state
- Statistical variance between fresh-boot 87.5% and unconstrained: **-0.3% to +2.7%**
- Hardware ceilings are immutable boundaries

---

## Scripts & Workflows

### Main Benchmarking Scripts

#### `run_benchmark.sh` - Full Model Suite
Comprehensive aging benchmark across all 6-7 models with optional thermal throttling.

```bash
# Usage
sudo ./scripts/run_benchmark.sh <duration_seconds> [--throttle <percentage>]

# Examples
sudo ./scripts/run_benchmark.sh 3600                    # 1 hour, no throttle
sudo ./scripts/run_benchmark.sh 86400 --throttle 50     # 24 hours, 50% CPU cap
sudo ./scripts/run_benchmark.sh 172800 --throttle 75    # 48 hours, thermal stress
```

**Models tested**: Qwen2.5 0.5B, Gemma2 2B, Phi-3 Mini, Llama 3.1 8B, Mistral 7B, DeepSeek-v2 Lite

See [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md#run_benchmarksh) for detailed usage.

#### `run_benchmark_pair.sh` - Dense vs MoE Comparison
Pairwise comparison with phase-aware metrics for statistical analysis.

```bash
sudo ./scripts/run_benchmark_pair.sh 172800 --throttle 62.5
```

Optimized for publication-quality results with separate prefill/decode throughput tracking.

See [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md#run_benchmark_pairsh) for detailed usage.

### Analytics & Visualization

#### `run_dashboard.sh` - Interactive Dashboard
Streamlit-based real-time visualization of benchmark results.

```bash
./scripts/run_dashboard.sh
# Access at http://localhost:8501
```

Features:
- Multi-date experiment comparison
- Phase-aware inference pipeline visualization
- Thermal & power telemetry graphs
- Raw CSV data explorer
- Export to PDF/SVG/PNG (configurable DPI)

#### `build_dashboard.py` - Core Analytics
Located in `src/build_dashboard.py`. Auto-loads:
- All `.csv` files from `logs/` directory
- 1 Hz physical power telemetry
- System resource metrics (CPU temp, RAM, TPS)
- Generates publication-ready figures

### Deployment & Sharing

#### `deploy_hf_spaces.sh` - Automated HF Spaces Deployment
Deploy dashboard to Hugging Face Spaces with GitHub auto-sync.

```bash
./scripts/deploy_hf_spaces.sh
# Follow interactive prompts to set up GitHub integration
```

Final dashboard URL: `https://huggingface.co/spaces/magnuscruz/llm-energy-tests`

See [DEPLOY_HF_SPACES.md](DEPLOY_HF_SPACES.md) for setup guide.

---

## Project Structure

```
llm-energy-tests/
├── README.md                      # This file
├── SCRIPTS_USAGE.md              # Comprehensive script documentation
├── DEPLOY_HF_SPACES.md           # HF Spaces deployment guide
├── requirements.txt              # Python dependencies
├── app.py                        # HF Spaces entry point
│
├── scripts/
│   ├── run_benchmark.sh          # Full model aging benchmark
│   ├── run_benchmark_pair.sh     # Dense vs MoE comparison
│   ├── run_dashboard.sh          # Launch visualization dashboard
│   ├── deploy_hf_spaces.sh       # HF Spaces automation
│   ├── run_clear.sh              # Log cleanup utility
│   └── run_tests.sh              # Quick validation tests
│
├── src/
│   ├── build_dashboard.py        # Streamlit dashboard (main)
│   ├── build_dashboard_*.py      # Alternative dashboard variants
│   ├── process_results.py        # CSV result aggregation
│   └── correlation_graph.py      # Statistical correlation analysis
│
└── logs/
    ├── YYYY-MM-DD/               # Daily experiment folder
    │   ├── warmup_logs/          # 10-min warm-up phase data
    │   │   ├── model_*_inference.csv
    │   │   ├── model_*_physical.csv
    │   │   └── model_*_system.csv
    │   └── deep_aging/           # Main 48-hour phase data
    │       ├── model_*_inference.csv
    │       ├── model_*_physical.csv
    │       └── model_*_system.csv
    └── [additional dated folders]
```

---

## CSV Output Formats

### `*_inference.csv` - Phase-Aware Metrics
```csv
timestamp,model,cpu_temp,ram_used_mb,prefill_tps,decode_tps
1715425200,llama3.1:8b,47.0,6475,295.66,12.33
1715425201,llama3.1:8b,47.5,6510,297.57,12.28
```

### `*_physical.csv` - 1 Hz Power Telemetry (Tapo P115)
```csv
Time,Watts
1715425200,148
1715425201,151
1715425202,143
```

### `*_system.csv` - System Resource Monitoring
```csv
Time,Temp,CPU_Load,RAM_MB
14:30:15,47.0,65.5,6475
14:30:16,47.5,68.2,6510
```

---

## Deployment

### Local Dashboard
```bash
# Terminal 1: Run benchmark
sudo ./scripts/run_benchmark.sh 3600

# Terminal 2: Launch dashboard
./scripts/run_dashboard.sh

# Access at http://localhost:8501
```

### Hugging Face Spaces (Cloud)
Automatic deployment with GitHub integration:

```bash
./scripts/deploy_hf_spaces.sh
git push origin main  # Triggers auto-deploy
```

Dashboard auto-updates on every push.

#### HF Spaces deploy checklist

1. Confirm repository includes:
   - `app.py`
   - `src/build_dashboard.py`
   - `src/requirements.txt`
   - `.streamlit/config.toml`
   - `.github/workflows/main.yml`
   - `logs/` if you want the dashboard to include data

2. Create the Space:
   - Visit: https://huggingface.co/new-space
   - Space name: `llm-energy-tests`
   - SDK: `Streamlit`
   - Visibility: `Public` or `Private`
   - License: choose your preferred license

3. Enable GitHub auto-deploy:
   - In the Space settings, open **Repository settings**
   - Enable **GitHub integration**
   - Connect repository: `magnuscruz/llm-energy-tests`
   - Auto-deploy branch: `main`

4. Push changes:

```bash
git add .
git commit -m "Deploy dashboard to HF Spaces"
git push origin main
```

5. Verify deployment:
   - Live URL: `https://huggingface.co/spaces/magnuscruz/llm-energy-tests`
   - See the Space **Logs** tab for build status

6. Notes:
   - If `logs/` is too large for Git, use Git LFS or external storage.
   - If the app loads but has no data, ensure `logs/` is present or update the dashboard to source remote data.
   - The workflow `.github/workflows/validate-hf-spaces.yml` validates app imports and syntax before deployment.

---

## Citation

If you use this research framework in your work, please cite:

```bibtex
@article{cruz2026software,
  title={Software Aging and Carbon-Aware Resilience in Edge-Deployed LLMs},
  author={Cruz, Magnus and Torquato, Matheus},
  journal={Department of Informatics Engineering, University of Coimbra},
  year={2026}
}
```

---

## Key References

- **Deployment Gauntlet Framework**: Grover et al., "Embodied Foundation Models at the Edge" (arXiv:2603.16952)
- **Software Aging Theory**: Torquato & Maciel, "Performance Degradation in Edge Nodes" (IEEE TDSC, 2024)
- **Carbon-Aware Metrics**: Rajashekar et al., "Sustainability-Aware LLM Inference" (arXiv:2502.14305)
- **Memory Management**: Kwon et al., "PagedAttention" (SOSP 2023)

---

## Support & Documentation

- **Detailed Script Usage**: See [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md)
- **Deployment Guide**: See [DEPLOY_HF_SPACES.md](DEPLOY_HF_SPACES.md)
- **GitHub Issues**: Report bugs and feature requests
- **Dashboard Features**: Documented in [src/build_dashboard.py](src/build_dashboard.py)

---

**Maintained by**: DEI Research Lab, University of Coimbra  
**Last Updated**: May 11, 2026