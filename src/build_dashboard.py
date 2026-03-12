import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import sys
import argparse

st.set_page_config(layout="wide")
st.title("🌡️ LLM Aging & Thermal Correlation")

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--date_filter', default=None, help='Filter by date (e.g., 20260311)')
args, _ = parser.parse_known_args()
date_filter = args.date_filter

# Load your LVM data
@st.cache_data
def load_and_merge(filter=None):
    print(f"Loading data with filter: {filter}")
    all_merged = []
    # Get subdirectory of logs
    log_dir = os.path.expanduser("~/git/llm-energy-tests/logs/{}".format(filter) \
                                  if filter else "~/git/llm-energy-tests/logs/")

    # Find all energy files
    energy_files = glob.glob(os.path.expanduser("{}/*energy_*.csv".format(log_dir)))
    
    for e_file in energy_files:
        # Match the corresponding temp file by timestamp/model
        t_file = e_file.replace("energy_", "temp_")
        if os.path.exists(t_file):
            df_e = pd.read_csv(e_file, names=['Time', 'Watts'])
            df_t = pd.read_csv(t_file) # Has Time, Temp headers
            
            # Merge on Time (Approximate if needed, but 1s intervals usually align)
            merged = pd.merge(df_e, df_t, on='Time')
            merged['Model'] = os.path.basename(e_file).split('_')[1]
            all_merged.append(merged)
    
    return pd.concat(all_merged) if all_merged else pd.DataFrame()

df = load_and_merge(date_filter)

if not df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Power vs Temperature (Correlation)")
        # Scatter plot shows if higher temps lead to higher power leakage
        fig_corr = px.scatter(df, x='Temp', y='Watts', color='Model', 
                             trendline="ols", title="Thermal Leakage Analysis")
        st.plotly_chart(fig_corr, use_container_width=True)

    with col2:
        st.subheader("Thermal Drift Over Time")
        fig_drift = px.line(df, x='Time', y='Temp', color='Model', 
                           title="CPU Temperature Progression")
        st.plotly_chart(fig_drift, use_container_width=True)
else:
    st.warning("No matched Energy/Temp logs found in ~/llm-energy-tests/logs/")
