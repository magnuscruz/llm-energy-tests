import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import plotly.io as pio

### --- Page Config ---
st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

### Custom CSS for DEI-FCTUC Aesthetics
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
</style>
""", unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.sidebar.header("DEI-FCTUC Research Filters")

### --- Configuration & Filters ---
KWH_PRICE = st.sidebar.slider("Electricity Cost (€/kWh)", 0.10, 0.50, 0.22)
base_path = os.path.expanduser("~/git/llm-energy-tests/logs/")

# Safely check if the base path exists
if not os.path.exists(base_path):
    st.error(f"Base path does not exist: {base_path}")
    st.stop()

available_dates = sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))], reverse=True)

if not available_dates:
    st.error(f"No log directories found in {base_path}")
    st.stop()

# Multiselect for combining two experiment folders
selected_dates = st.sidebar.multiselect(
    "Select Experiment Dates (Max 2)", 
    options=available_dates, 
    default=available_dates[:2] if len(available_dates) >= 2 else available_dates,
    max_selections=2
)

### --- Publication Export Settings ---
st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

# --- Data Loader (Updated to Merge Inference and System Data) ---
@st.cache_data
def load_research_data(date_folders):
    all_dfs = []
    for date_folder in date_folders:
        log_dir = os.path.join(base_path, date_folder)
        # Target the inference files first
        inference_files = glob.glob(f"{log_dir}/*_inference.csv")
        
        for inf_file in inference_files:
            # 1. Read the Inference Data (Contains TPS)
            df_inf = pd.read_csv(inf_file)
            
            # 2. Find and read the matching System Data (Contains Temp, RAM_MB, CPU_Load)
            sys_file = inf_file.replace('_inference.csv', '_system.csv')
            
            if os.path.exists(sys_file):
                df_sys = pd.read_csv(sys_file)
                # Merge the two DataFrames on the 'Time' column
                df_temp = pd.merge(df_inf, df_sys, on='Time', how='inner')
            else:
                # Fallback if the system file is missing
                df_temp = df_inf
                
            # Optional: Find and merge the Physical Data (Contains Watts) if it exists
            phys_file = inf_file.replace('_inference.csv', '_physical.csv')
            if os.path.exists(phys_file):
                df_phys = pd.read_csv(phys_file)
                df_temp = pd.merge(df_temp, df_phys, on='Time', how='inner')
            
            df_temp['Experiment_Folder'] = date_folder
            
            # 3. Model name extraction
            if 'Model' not in df_temp.columns:
                # e.g., 'deepseek-v2_lite_035438_inference.csv'
                base_name = os.path.basename(inf_file).replace('_inference.csv', '')
                parts = base_name.split('_')
                # Keep everything except the timestamp (the last part)
                model_name = '_'.join(parts[:-1]) 
                
                df_temp['Model'] = model_name
                
            all_dfs.append(df_temp)
            
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()

### --- Main Logic ---
if selected_dates:
    df = load_research_data(selected_dates)

    if not df.empty:
        # Model selection via checkboxes
        st.sidebar.divider()
        st.sidebar.subheader("Select Models")
        
        available_models = sorted(df['Model'].unique())
        selected_models = []
        
        for model in available_models:
            if st.sidebar.checkbox(model, value=True):
                selected_models.append(model)
                
        # Filter dataframe by checked models
        filtered_df = df[df['Model'].isin(selected_models)]
        
        if filtered_df.empty:
            st.warning("Please select at least one model from the sidebar to view data.")
        else:
            # KPI Row 
            m1, m2, m3, m4 = st.columns(4)
            
            # Safely render metrics if columns exist after the merge
            if 'TPJ' in filtered_df.columns:
                m1.metric("Avg TPJ", f"{filtered_df['TPJ'].mean():.2f}", help="Tokens per Joule")
            else:
                m1.metric("Avg TPJ", "N/A")
                
            if 'Leakage_Delta' in filtered_df.columns:
                m2.metric("Thermal Leakage (Avg)", f"{filtered_df['Leakage_Delta'].mean():.1f} W", delta=f"{filtered_df['Leakage_Delta'].max():.1f} W Max")
            else:
                m2.metric("Thermal Leakage (Avg)", "N/A")
                
            if 'Temp' in filtered_df.columns:
                m3.metric("Mean Temp", f"{filtered_df['Temp'].mean():.1f} °C")
            
            if 'TPS' in filtered_df.columns:
                m4.metric("Avg TPS", f"{filtered_df['TPS'].mean():.2f} t/s")
            
            st.divider()
            
            # Generate the comparative graph mapping Temp vs TPS
            if 'Temp' in filtered_df.columns and 'TPS' in filtered_df.columns:
                st.subheader("Comparative Analysis: Temperature vs. TPS")
                
                # Colors map to models, symbols map to the experimental folder to compare runs
                fig = px.scatter(
                    filtered_df, 
                    x="Temp", 
                    y="TPS", 
                    color="Model", 
                    symbol="Experiment_Folder",
                    title="Throughput Decay by Hardware Temperature",
                    labels={"Temp": "Hardware Temperature (°C)", "TPS": "Tokens per Second (TPS)"},
                    template="plotly_dark",
                    hover_data=['Time', 'RAM_MB'] if 'RAM_MB' in filtered_df.columns else None
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Missing 'Temp' or 'TPS' columns in the dataset for visualization. Ensure _system.csv files are present.")
    else:
        st.error("No valid research logs found for the selected dates.")
else:
    st.warning("Please select at least one experiment folder.")