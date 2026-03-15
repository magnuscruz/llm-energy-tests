import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import glob
import os
import argparse

st.set_page_config(layout="wide", page_title="LLM Aging & Performance Dashboard")
st.title("🌡️ LLM Aging & Thermal Correlation")

# --- Configuration & Arguments ---
parser = argparse.ArgumentParser()
parser.add_argument('--date_filter', default=None, help='Filter by date (e.g., 20260311)')
args, _ = parser.parse_known_args()
date_filter = args.date_filter

# Electricity price (Portugal average approx €0.22/kWh)
KWH_PRICE = 0.22 

@st.cache_data
def load_and_merge(filter=None):
    all_merged = []
    base_path = "~/git/llm-energy-tests/logs/" 
    log_dir = os.path.expanduser(base_path + (filter if filter else ""))

    energy_files = glob.glob(f"{log_dir}/energy_*.csv")
    
    for e_file in energy_files:
        t_file = e_file.replace("energy_", "temp_")
        r_file = e_file.replace("energy_", "resp_")
        s_file = e_file.replace("energy_", "system_") # New System Metrics
        
        if all(os.path.exists(f) for f in [t_file, r_file, s_file]):
            df_e = pd.read_csv(e_file, names=['Time', 'Watts'])
            df_t = pd.read_csv(t_file)
            df_r = pd.read_csv(r_file)
            df_s = pd.read_csv(s_file) # Headers: Time, CPU_Usage, RAM_Used_MB
            
            # Merging all 4 data sources
            merged = pd.merge(df_e, df_t, on='Time')
            merged = pd.merge(merged, df_r, on='Time')
            merged = pd.merge(merged, df_s, on='Time')
            
            merged['Model'] = os.path.basename(e_file).split('_')[1]
            
            # Index logic for Sample alignment
            merged = merged.reset_index().rename(columns={'index': 'Sample'})
            
            # --- Calculations from Image ---
            # 1. Hardware Energy Estimation (Software + 15% board/VRM overhead)
            merged['Watts_HW'] = merged['Watts'] * 1.15
            # 2. Cost per 1M tokens: (Watts/1000) * (Hours to gen 1M tokens) * Price
            merged['Cost_1M'] = (merged['Watts'] / 1000) * (1000000 / ( (1/merged['Latency']) * 3600)) * KWH_PRICE
            
            all_merged.append(merged)
    
    return pd.concat(all_merged) if all_merged else pd.DataFrame()

df = load_and_merge(date_filter)

if not df.empty:
    # --- TOP ROW: KPI Summary (Based on Image Blocks) ---
    st.subheader("📊 Key Performance Indicators (Consolidated Benchmark)")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    
    m1.metric("Energy (Software)", f"{df['Watts'].mean():.1f} W")
    m2.metric("Max Temp", f"{df['Temp'].max():.1f} °C")
    m3.metric("Energy (Hardware Est.)", f"{df['Watts_HW'].mean():.1f} W")
    m4.metric("Avg Latency", f"{df['Latency'].mean()*1000:.0f} ms")
    m5.metric("Avg RAM Usage", f"{df['RAM_Used_MB'].mean():.0f} MB")
    m6.metric("Cost / 1M Tokens", f"€{df['Cost_1M'].mean():.4f}", delta_color="inverse")

    if df['Temp'].max() > 85:
        st.error(f"⚠️ Critical Thermal Alert: Peak reached {df['Temp'].max()}°C")

    st.divider()

    # --- Charts Row 1: Energy & Thermal ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Thermal Leakage Analysis")
        fig_corr = px.scatter(df, x='Temp', y='Watts', color='Model', trendline="ols")
        
        fig_global = px.scatter(df, x='Temp', y='Watts', trendline="ols", trendline_color_override="black")
        if len(fig_global.data) > 1:
            global_trend = fig_global.data[1]
            global_trend.name = "Hardware Baseline Trend"
            global_trend.line.dash = "dot"
            fig_corr.add_trace(global_trend)
        st.plotly_chart(fig_corr, use_container_width=True)

    with col2:
        st.subheader("Thermal Progression (Sample Index)")
        fig_drift = px.line(df, x='Sample', y='Temp', color='Model')
        fig_drift.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Throttling Zone")
        st.plotly_chart(fig_drift, use_container_width=True)

    # --- Charts Row 2: Performance & Resources ---
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("⏱️ Inference Latency (Response Time)")
        fig_lat = px.line(df, x='Sample', y='Latency', color='Model', labels={'Latency': 'Seconds'})
        st.plotly_chart(fig_lat, use_container_width=True)
        
    with col4:
        st.subheader("💻 System Resource Usage (CPU & RAM)")
        # Plotting both CPU and RAM could be busy, let's focus on RAM aging
        fig_res = px.line(df, x='Sample', y='RAM_Used_MB', color='Model', title="RAM Stability Over Time")
        st.plotly_chart(fig_res, use_container_width=True)

    with st.expander("View Full Metric Table"):
        st.dataframe(df.sort_values(by=['Model', 'Sample']))

else:
    st.warning("No complete logs found. Ensure you are running the latest version of benchmark.sh with system metrics enabled.")
