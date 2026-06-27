import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# ==============================================================================
# DEI Research Benchmark - LLM Sustainability Lab Dashboard
# ==============================================================================
st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

st.markdown("""
<style>
    .reportview-container { background: #f0f2f6; }
    .sidebar .sidebar-content { background: #ffffff; }
</style>
""", unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.markdown("### Ecological Efficiency under Continuous Edge Inference (48h Gauntlet)")

st.sidebar.header("DEI-FCTUC Research Filters")

@st.cache_data
def load_telemetry_data(data_directory):
    """
    Scans the directory and subdirectories for merged telemetry CSVs and parses the model architecture,
    deployment scenario, and test baseline from filenames and directory paths.
    """
    file_pattern = os.path.join(data_directory, "**", "*_merged_analysis.csv")
    csv_files = glob.glob(file_pattern, recursive=True)
    
    data_frames = []
    for file in csv_files:
        filename = os.path.basename(file)
        file_dir = os.path.dirname(file)
        
        # Load dataset
        df = pd.read_csv(file)
        
        # 1. Parse Architecture
        if "phi3_mini" in filename: 
            architecture = "Phi-3 Mini (3.8B - Packed Dense)"
        elif "llama3.1_8b" in filename: 
            architecture = "Llama 3.1 (8B - Mid-Weight Dense)"
        elif "deepseek-v2_lite" in filename: 
            architecture = "DeepSeek-v2 Lite (16B - Sparse MoE)"
        elif "qwen2.5_0.5b" in filename: 
            architecture = "Qwen2.5 (0.5B - Ultra-Light Dense)"
        else:
            architecture = "Unknown Model"
            
        # 2. Parse Execution Scenario (from filename)
        if "_R1_" in filename: 
            scenario = "R1 (Pristine Ambient)"
        elif "_R2_" in filename: 
            scenario = "R2 (Thermal Anomaly)"
        elif "throttle_87_5" in filename: 
            scenario = "Throttled (87.5% Placebo Cap)"
        else:
            scenario = "Baseline"
        
        # 3. Parse Test Baseline from directory name
        # Traverse up directory tree to find the baseline directory (contains date prefix like "2026-05-01_")
        test_baseline = "Unknown"
        current_dir = file_dir
        for _ in range(5):  # Traverse up max 5 levels
            dir_basename = os.path.basename(current_dir)
            if dir_basename and "_" in dir_basename and any(c.isdigit() for c in dir_basename.split("_")[0]):
                # Found a directory with date prefix (e.g., "2026-05-01_48h_R1_no_throtting")
                test_baseline = "_".join(dir_basename.split("_")[1:]) if "_" in dir_basename else dir_basename
                break
            current_dir = os.path.dirname(current_dir)
            if current_dir == os.path.dirname(current_dir):  # Reached root
                break
            
        df["Architecture"] = architecture
        df["Scenario"] = scenario
        df["Test_Baseline"] = test_baseline
        df["Legend"] = f"{architecture} | {scenario}"
        df["Legend_with_baseline"] = f"{architecture} | {scenario} | {test_baseline}"
        
        # 3. Create Relative Timeline (Hours)
        df["Time (Hours)"] = (df["timestamp"] - df["timestamp"].min()) / 3600.0
        
        # Drop anomalous NaNs that might occur at the tail of log files
        df = df.dropna(subset=["cpu_temp", "decode_tps", "ram_used_mb", "eco_efficiency_ce"])
        
        data_frames.append(df)
        
    if data_frames:
        return pd.concat(data_frames, ignore_index=True)
    return pd.DataFrame()

# --- Configuration & Filters ---
# Default to current directory data folder, update as necessary
data_path = st.sidebar.text_input("Data Directory Path:", value="./logs/")

if not os.path.exists(data_path):
    st.warning(f"Awaiting valid dataset directory. Place `*_merged_analysis.csv` files in: {data_path}")
    st.stop()

# Load and process files
df_master = load_telemetry_data(data_path)

if df_master.empty:
    st.error("No compatible `_merged_analysis.csv` datasets found in the directory.")
    st.stop()

# Filter Controls
st.sidebar.subheader("Execution Parameters")
selected_models = st.sidebar.multiselect(
    "Select Model Architectures:", 
    options=df_master["Architecture"].unique(),
    default=df_master["Architecture"].unique()
)

scenario_options = df_master["Scenario"].unique()
scenario_defaults = [s for s in ["R1 (Pristine Ambient)", "Throttled (87.5% Placebo Cap)"] if s in scenario_options]
# Fallback to first scenario if preferred defaults aren't available
if not scenario_defaults and len(scenario_options) > 0:
    scenario_defaults = [scenario_options[0]]

selected_scenarios = st.sidebar.multiselect(
    "Select Testing Scenarios:", 
    options=scenario_options,
    default=scenario_defaults
)

smoothing_window = st.sidebar.slider("Moving Average Smoothing (Matches Methodology):", min_value=1, max_value=200, value=60, step=10, help="Applies a rolling window to smooth 1Hz execution jitter.")

# Comparison Mode
st.sidebar.markdown("---")
st.sidebar.subheader("Baseline Comparison Mode")
enable_comparison = st.sidebar.checkbox("Enable Comparison Analysis", value=False, help="Compare metrics between two different test baselines")

# Comparison baseline multiselect
comparison_baselines = []

if enable_comparison:
    available_baselines = sorted(df_master["Test_Baseline"].unique())
    comparison_baselines = st.sidebar.multiselect(
        "Select Baselines:",
        options=available_baselines,
        default=available_baselines,
        help="Compare multiple test baselines together."
    )

# Apply Filters
if enable_comparison and comparison_baselines:
    df_filtered = df_master[
        (df_master["Architecture"].isin(selected_models)) & 
        (df_master["Scenario"].isin(selected_scenarios)) &
        (df_master["Test_Baseline"].isin(comparison_baselines))
    ].copy()
else:
    df_filtered = df_master[
        (df_master["Architecture"].isin(selected_models)) & 
        (df_master["Scenario"].isin(selected_scenarios))
].copy()

if df_filtered.empty:
    st.info("No telemetry matching the selected filters.")
    st.stop()

# Apply Smoothing
if smoothing_window > 1:
    numeric_cols = ["cpu_temp", "ram_used_mb", "decode_tps", "prefill_tps", "watts_mean", "eco_efficiency_ce", "tokens_per_joule"]
    # Group by exact execution run to prevent smoothing across different tests
    df_filtered[numeric_cols] = df_filtered.groupby("Legend")[numeric_cols].transform(lambda x: x.rolling(smoothing_window, min_periods=1).mean())

# --- Dashboard Visualizations ---

st.markdown("---")
st.subheader("1. Thermodynamic Redlining vs. Thermal Breathing Room")
st.markdown("Tracks localized hardware temperature (`cpu_temp`). Highlights the catastrophic 64°C limits for packed dense models and the sparse power fluctuations of MoE.")
color_column = "Legend_with_baseline" if enable_comparison else "Legend"
fig_temp = px.line(df_filtered, x="Time (Hours)", y="cpu_temp", color=color_column, 
                   labels={"cpu_temp": "CPU Temperature (°C)"}, template="plotly_white")
fig_temp.add_hline(y=63.0, line_dash="dot", line_color="red", annotation_text="Critical Thermal Ceiling")
st.plotly_chart(fig_temp, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("2. Memory-Bound Software Aging")
    st.markdown("Monitors `ram_used_mb`. Exposes the active sawtooth oscillation of Llama 3.1 and the flatlining MLA stability of DeepSeek-v2.")
    fig_ram = px.line(df_filtered, x="Time (Hours)", y="ram_used_mb", color=color_column, 
                      labels={"ram_used_mb": "RAM Usage (MB)"}, template="plotly_white")
    st.plotly_chart(fig_ram, use_container_width=True)

with col2:
    st.subheader("3. Execution Jitter & Degradation")
    st.markdown("Autoregressive Decode Throughput (`decode_tps`). Exposes End-of-Sequence (EOS) attention crashes under thermal stress.")
    fig_tps = px.line(df_filtered, x="Time (Hours)", y="decode_tps", color=color_column, 
                      labels={"decode_tps": "Decode Throughput (TPS)"}, template="plotly_white")
    st.plotly_chart(fig_tps, use_container_width=True)

st.markdown("---")
st.subheader("4. Carbon-Aware Eco-Efficiency Metric (CAE2M)")
st.markdown("The global sustainability benchmark mapping hardware power draw against grid intensity (`eco_efficiency_ce`). Assesses Tokens/gCO₂eq.")
fig_ce = px.line(df_filtered, x="Time (Hours)", y="eco_efficiency_ce", color=color_column, 
                 labels={"eco_efficiency_ce": "Carbon Eco-Efficiency (CE)"}, template="plotly_white")
st.plotly_chart(fig_ce, use_container_width=True)

# --- Comparative Benchmark: Speed vs. Sustainability ---
st.markdown("---")

if enable_comparison and comparison_baselines:
    baseline_label = " vs. ".join(comparison_baselines)
    st.subheader(f"5. Baseline Comparison: {baseline_label}")
    st.markdown(f"""
    **Direct comparison** of performance and sustainability metrics across the selected test baselines.
    - **Selected baselines:** {', '.join(comparison_baselines)}
    
    This analysis reveals how different operational conditions impact speed, power consumption, and efficiency across all tested architectures.
    """)
    
    # Aggregate metrics by Architecture and Test_Baseline for comparative analysis
    summary_comparison = df_filtered.groupby(["Architecture", "Test_Baseline"]).agg({
        "decode_tps": "mean",
        "watts_mean": "mean",
        "tokens_per_joule": "mean"
    }).reset_index()
    summary_comparison.columns = ["Architecture", "Test_Baseline", "Avg Decode TPS", "Avg Power (W)", "Avg Efficiency (Tokens/Joule)"]
    
    col_tps, col_power, col_eff = st.columns(3)
    
    with col_tps:
        st.markdown("### 📊 Decode Throughput (TPS)")
        st.markdown("Processing speed comparison.")
        fig_tps_bar = px.bar(summary_comparison, x="Architecture", y="Avg Decode TPS", color="Test_Baseline", 
                             barmode="group", template="plotly_white", text_auto=".2f",
                             labels={"Avg Decode TPS": "Tokens/Second", "Architecture": "Model Architecture", "Test_Baseline": "Baseline"})
        fig_tps_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_tps_bar, use_container_width=True)
    
    with col_power:
        st.markdown("### ⚡ Power Consumption (W)")
        st.markdown("Energy draw comparison.")
        fig_power_bar = px.bar(summary_comparison, x="Architecture", y="Avg Power (W)", color="Test_Baseline", 
                               barmode="group", template="plotly_white", text_auto=".2f",
                               labels={"Avg Power (W)": "Watts", "Architecture": "Model Architecture", "Test_Baseline": "Baseline"})
        fig_power_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_power_bar, use_container_width=True)
    
    with col_eff:
        st.markdown("### 🌱 Efficiency (Tokens/Joule)")
        st.markdown("Sustainability metric comparison.")
        fig_eff_bar = px.bar(summary_comparison, x="Architecture", y="Avg Efficiency (Tokens/Joule)", color="Test_Baseline", 
                             barmode="group", template="plotly_white", text_auto=".3f",
                             labels={"Avg Efficiency (Tokens/Joule)": "Tokens/Joule", "Architecture": "Model Architecture", "Test_Baseline": "Baseline"})
        fig_eff_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_eff_bar, use_container_width=True)
        
else:
    st.subheader("5. Comparative Edge AI Benchmark: Speed-Sustainability Trade-off Analysis")
    st.markdown("""
    This analysis examines how operational changes (aging, throttling, thermal stress) impact the **speed-sustainability nexus**. 
    Metrics shown: **Decode Throughput (TPS)** reflects processing speed; **Power (W)** shows energy consumption; 
    **Efficiency (Tokens/Joule)** quantifies the trade-off. The goal is to identify which architectures maintain **resilience** under degraded conditions.
    """)
    
    # Aggregate metrics by Architecture and Scenario for comparative analysis
    summary_by_arch_scenario = df_filtered.groupby(["Architecture", "Scenario"]).agg({
        "decode_tps": "mean",
        "watts_mean": "mean",
        "tokens_per_joule": "mean"
    }).reset_index()
    summary_by_arch_scenario.columns = ["Architecture", "Scenario", "Avg Decode TPS", "Avg Power (W)", "Avg Efficiency (Tokens/Joule)"]
    
    col_tps, col_power, col_eff = st.columns(3)
    
    with col_tps:
        st.markdown("### 📊 Decode Throughput (TPS)")
        st.markdown("Processing speed across architectures and conditions.")
        fig_tps_bar = px.bar(summary_by_arch_scenario, x="Architecture", y="Avg Decode TPS", color="Scenario", 
                             barmode="group", template="plotly_white", text_auto=".2f",
                             labels={"Avg Decode TPS": "Tokens/Second", "Architecture": "Model Architecture"})
        fig_tps_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_tps_bar, use_container_width=True)
    
    with col_power:
        st.markdown("### ⚡ Power Consumption (W)")
        st.markdown("Energy draw across conditions.")
        fig_power_bar = px.bar(summary_by_arch_scenario, x="Architecture", y="Avg Power (W)", color="Scenario", 
                               barmode="group", template="plotly_white", text_auto=".2f",
                               labels={"Avg Power (W)": "Watts", "Architecture": "Model Architecture"})
        fig_power_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_power_bar, use_container_width=True)
    
    with col_eff:
        st.markdown("### 🌱 Efficiency (Tokens/Joule)")
        st.markdown("Sustainability metric: speed per unit energy.")
        fig_eff_bar = px.bar(summary_by_arch_scenario, x="Architecture", y="Avg Efficiency (Tokens/Joule)", color="Scenario", 
                             barmode="group", template="plotly_white", text_auto=".3f",
                             labels={"Avg Efficiency (Tokens/Joule)": "Tokens/Joule", "Architecture": "Model Architecture"})
        fig_eff_bar.update_layout(height=400, showlegend=True, hovermode="x unified")
        st.plotly_chart(fig_eff_bar, use_container_width=True)

# --- Summary Statistics Table ---
st.markdown("---")
st.markdown("### Aggregated Execution Statistics (48-Hour Run)")
legend_col = "Legend_with_baseline" if enable_comparison else "Legend"
summary_df = df_filtered.groupby(legend_col).agg({
    "cpu_temp": ["max", "mean"],
    "ram_used_mb": "max",
    "decode_tps": "mean",
    "watts_mean": "mean",
    "eco_efficiency_ce": "mean"
}).round(2)
summary_df.columns = ["Peak Temp (°C)", "Avg Temp (°C)", "Peak RAM (MB)", "Avg Decode TPS", "Avg Power (W)", "Avg Eco-Efficiency (CE)"]
st.dataframe(summary_df, use_container_width=True)

# Raw Data Expander
with st.expander("View Raw Telemetry Output"):
    st.dataframe(df_filtered.head(1000))