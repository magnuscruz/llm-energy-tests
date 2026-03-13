import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import glob
import os
import argparse

st.set_page_config(layout="wide", page_title="LLM Thermal Dashboard")
st.title("🌡️ LLM Aging & Thermal Correlation")

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--date_filter', default=None, help='Filter by date (e.g., 20260311)')
args, _ = parser.parse_known_args()
date_filter = args.date_filter

@st.cache_data
def load_and_merge(filter=None):
    all_merged = []
    base_path = "~/llm-energy-tests/logs/" 
    log_dir = os.path.expanduser(base_path + (filter if filter else ""))

    energy_files = glob.glob(f"{log_dir}/energy_*.csv")
    
    for e_file in energy_files:
        t_file = e_file.replace("energy_", "temp_")
        r_file = e_file.replace("energy_", "resp_") # Response time file
        
        if os.path.exists(t_file) and os.path.exists(r_file):
            df_e = pd.read_csv(e_file, names=['Time', 'Watts'])
            df_t = pd.read_csv(t_file) # Headers: Time, Temp
            df_r = pd.read_csv(r_file) # Headers: Time, Latency
            
            # Merge Energy, Temp, and Latency on Time
            merged = pd.merge(df_e, df_t, on='Time')
            merged = pd.merge(merged, df_r, on='Time')
            
            merged['Model'] = os.path.basename(e_file).split('_')[1]
            
            # Index logic for Sample alignment
            merged = merged.reset_index().rename(columns={'index': 'Sample'})
            all_merged.append(merged)
    
    return pd.concat(all_merged) if all_merged else pd.DataFrame()

df = load_and_merge(date_filter)

if not df.empty:
    # --- Top Row Metrics ---
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Avg Temp", f"{df['Temp'].mean():.1f} °C")
    m2.metric("Max Temp", f"{df['Temp'].max():.1f} °C")
    m3.metric("Avg Power", f"{df['Watts'].mean():.1f} W")
    m4.metric("Avg Latency", f"{df['Latency'].mean():.2f}s")
    m5.metric("Models Tested", len(df['Model'].unique()))

    if df['Temp'].max() > 90:
        st.error(f"⚠️ High Temperature Warning: System reached {df['Temp'].max()}°C")

    # --- Charts Row 1: Thermal and Power ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Thermal Leakage Analysis (Power vs Temp)")
        fig_corr = px.scatter(df, x='Temp', y='Watts', color='Model', 
                             trendline="ols", title="Per-Model Leakage")
        
        fig_global = px.scatter(df, x='Temp', y='Watts', trendline="ols",
                               trendline_color_override="black")
        if type(fig_global) == go.Figure and len(fig_global.data) > 1:
            global_trend = fig_global.data[1]
            global_trend.name = "Global Hardware Trend"
            global_trend.line.dash = "dot"
            fig_corr.add_trace(global_trend)
            
        st.plotly_chart(fig_corr, use_container_width=True)

    with col2:
        st.subheader("Thermal Progression (Sample Index)")
        fig_drift = px.line(df, x='Sample', y='Temp', color='Model', 
                           labels={'Sample': 'Sample Number', 'Temp': 'Temperature (°C)'},
                           title="CPU Heating Curve")
        fig_drift.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Throttling Zone")
        st.plotly_chart(fig_drift, use_container_width=True)

    # --- Charts Row 2: Performance/Latency ---
    st.divider()
    st.subheader("⏱️ Inference Latency Analysis")
    fig_lat = px.line(df, x='Sample', y='Latency', color='Model',
                     labels={'Sample': 'Sample Number', 'Latency': 'Response Time (s)'},
                     title="Latency Stability (Response Time per Sample)")
    st.plotly_chart(fig_lat, use_container_width=True)
        
    with st.expander("View Consolidated Data Table"):
        st.dataframe(df.sort_values(by=['Model', 'Sample']))

else:
    st.warning("No matched logs (Energy + Temp + Latency) found.")
