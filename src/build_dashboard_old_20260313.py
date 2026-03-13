# Build a Streamlit dashboard to visualize the correlation between CPU temperature and power consumption for LLM aging tests.
# This dashboard will read the energy and temperature logs, merge them, and create interactive plots to analyze the thermal leakage and aging effects on LLMs.

import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import argparse

st.set_page_config(layout="wide")
st.title("🌡️ LLM Aging & Thermal Correlation")

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--date_filter', default=None, help='Filter by date (e.g., 20260311)')
args, _ = parser.parse_known_args()
date_filter = args.date_filter

@st.cache_data
def load_and_merge(filter=None):
    all_merged = []
    # Adjust directory based on filter
    base_path = "~/git/llm-energy-tests/logs/"
    log_dir = os.path.expanduser(f"{base_path}{filter}" if filter else base_path)

    energy_files = glob.glob(f"{log_dir}/*energy_*.csv")
    
    for e_file in energy_files:
        t_file = e_file.replace("energy_", "temp_")
        if os.path.exists(t_file):
            # Load Power and Temperature
            df_e = pd.read_csv(e_file, names=['Time', 'Watts'])
            df_t = pd.read_csv(t_file) # Expects headers: Time, Temp
            
            # Merge and clean
            merged = pd.merge(df_e, df_t, on='Time')
            # Extracting model name (assuming format: energy_MODELNAME_TIMESTAMP.csv)
            merged['Model'] = os.path.basename(e_file).split('_')[1]
            
            # --- INDEX LOGIC START ---
            # Create a sequential index (0, 1, 2...) for this specific file/run
            merged = merged.reset_index().rename(columns={'index': 'Sample'})
            # --- INDEX LOGIC END ---
            
            all_merged.append(merged)
    
    return pd.concat(all_merged) if all_merged else pd.DataFrame()

df = load_and_merge(date_filter)

if not df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Power vs Temperature (Correlation)")
        fig_corr = px.scatter(df, x='Temp', y='Watts', color='Model', 
                             trendline="ols", title="Thermal Leakage Analysis")
        st.plotly_chart(fig_corr, use_container_width=True)

    with col2:
        st.subheader("Thermal Progression (Sample Index)")
        # Changing x from 'Time' to 'Sample'
        fig_drift = px.line(df, x='Sample', y='Temp', color='Model', 
                           labels={'Sample': 'Elapsed Seconds', 'Temp': 'Temperature (°C)'},
                           title="CPU Temperature Progression per Model")
        st.plotly_chart(fig_drift, use_container_width=True)
        
    # Optional: Full Data Table
    with st.expander("View Raw Data"):
        st.dataframe(df)
else:
    st.warning(f"No logs found in {date_filter if date_filter else 'root logs'}. Check your path or date filter.")
