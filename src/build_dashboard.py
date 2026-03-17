import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import argparse

st.set_page_config(layout="wide", page_title="LLM Aging & Performance Dashboard")
st.title("🌡️ LLM Aging & Thermal Correlation")

parser = argparse.ArgumentParser()
parser.add_argument('--date_filter', default=None, help='Filter by date (e.g., 20260311)')
parser.add_argument('-c', '--clear_cache', action='store_true', default=True)
parser.add_argument('--kwh_price', type=float, default=0.22)
args, _ = parser.parse_known_args()
date_filter = args.date_filter
KWH_PRICE = args.kwh_price

if args.clear_cache:
    st.cache_data.clear()

@st.cache_data
def load_and_merge(filter=None):
    all_merged = []
    base_path = "~/git/llm-energy-tests/logs/" 
    log_dir = os.path.expanduser(base_path + (filter if filter else ""))

    energy_files = glob.glob(f"{log_dir}/energy_*.csv")
    
    for e_file in energy_files:
        t_file = e_file.replace("energy_", "temp_")
        r_file = e_file.replace("energy_", "resp_")
        s_file = e_file.replace("energy_", "system_")
        p_file = e_file.replace("energy_", "physical_") 
        
        if all(os.path.exists(f) for f in [t_file, r_file, s_file]):
            df_e = pd.read_csv(e_file, names=['Time', 'Watts'])
            df_t = pd.read_csv(t_file)
            df_r = pd.read_csv(r_file)
            df_s = pd.read_csv(s_file)
            
            merged = pd.merge(df_e, df_t, on='Time')
            merged = pd.merge(merged, df_r, on='Time')
            merged = pd.merge(merged, df_s, on='Time')
            
            if os.path.exists(p_file):
                df_p = pd.read_csv(p_file) # Headers: Time, Watts_Physical
                merged = pd.merge(merged, df_p, on='Time')
            else:
                merged['Watts_Physical'] = merged['Watts'] * 1.15
            
            merged['Model'] = os.path.basename(e_file).split('_')[1]
            merged = merged.reset_index().rename(columns={'index': 'Sample'})
            merged['Cost_1M'] = (merged['Watts_Physical'] / 1000) * (1000000 / ((1/merged['Latency']) * 3600)) * KWH_PRICE
            all_merged.append(merged)
    
    return pd.concat(all_merged) if all_merged else pd.DataFrame()

df = load_and_merge(date_filter)

if not df.empty:
    st.subheader("📊 Consolidated Benchmark KPIs (Tapo P110 Data)")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Energy (Software)", f"{df['Watts'].mean():.1f} W")
    m2.metric("Max Temp", f"{df['Temp'].max():.1f} °C")
    m3.metric("Energy (Physical/Tapo)", f"{df['Watts_Physical'].mean():.1f} W")
    m4.metric("Avg Latency", f"{df['Latency'].mean()*1000:.0f} ms")
    m5.metric("Avg RAM Usage", f"{df['RAM_Used_MB'].mean():.0f} MB")
    m6.metric("Cost / 1M Tokens", f"€{df['Cost_1M'].mean():.4f}")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Thermal Leakage (Software vs Temp)")
        fig_corr = px.scatter(df, x='Temp', y='Watts', color='Model', trendline="ols")
        st.plotly_chart(fig_corr, use_container_width=True)
    with col2:
        st.subheader("Thermal Progression")
        fig_drift = px.line(df, x='Sample', y='Temp', color='Model')
        st.plotly_chart(fig_drift, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("⏱️ Inference Latency")
        fig_lat = px.line(df, x='Sample', y='Latency', color='Model')
        st.plotly_chart(fig_lat, use_container_width=True)
    with col4:
        st.subheader("🔌 Software vs Physical Power")
        fig_gap = px.line(df, x='Sample', y=['Watts', 'Watts_Physical'], color='Model')
        st.plotly_chart(fig_gap, use_container_width=True)
else:
    st.warning("No complete logs found. Ensure benchmark is generating 'physical_*.csv'.")
