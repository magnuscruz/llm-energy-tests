import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import plotly.io as pio

# ==============================================================================
# DEI Research Benchmark - LLM Sustainability Lab Dashboard
# ==============================================================================

# --- Page Config ---
st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

# Custom CSS for DEI-FCTUC Aesthetics
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.sidebar.header("DEI-FCTUC Research Filters")

# --- Configuration & Filters ---
KWH_PRICE = st.sidebar.slider("Electricity Cost (€/kWh)", 0.10, 0.50, 0.22)
base_path = os.path.expanduser("~/git/llm-energy-tests/logs/")

if not os.path.exists(base_path):
    st.error(f"Base path does not exist: {base_path}")
    st.stop()

# Find all valid date directories
available_dates = sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))], reverse=True)

if not available_dates:
    st.error(f"No log directories found in {base_path}")
    st.stop()

selected_dates = st.sidebar.multiselect(
    "Select Experiment Dates (Max 2)",
    options=available_dates,
    default=available_dates[:2] if len(available_dates) >= 2 else available_dates,
    max_selections=2
)

# --- Publication Export Settings ---
st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

@st.cache_data
def load_research_data(date_folders):
    all_inference = []
    all_system = []
    all_physical = []
    
    for date_folder in date_folders:
        log_dir = os.path.join(base_path, date_folder)
        
        # Recursive search handles both Flat and Nested directory structures
        inference_files = glob.glob(os.path.join(log_dir, "**", "*_inference.csv"), recursive=True)
        system_files = glob.glob(os.path.join(log_dir, "**", "*_system.csv"), recursive=True)
        physical_files = glob.glob(os.path.join(log_dir, "**", "*_physical.csv"), recursive=True)
        
        # Process Inference Logs
        for file in inference_files:
            df = pd.read_csv(file)
            basename = os.path.basename(file)
            model_name = "_".join(basename.split("_")[:-2]) 
            
            if "warmup_logs" in file:
                phase = "Warm-up"
            elif "deep_aging" in file:
                phase = "Deep Aging"
            else:
                phase = "Uncategorized (Flat)"
                
            df['Model'] = model_name
            df['Phase'] = phase
            df['Date'] = date_folder
            all_inference.append(df)
            
        # Process System Logs
        for file in system_files:
            df = pd.read_csv(file)
            basename = os.path.basename(file)
            model_name = "_".join(basename.split("_")[:-2])
            phase = "Warm-up" if "warmup_logs" in file else "Deep Aging" if "deep_aging" in file else "Uncategorized (Flat)"
            
            df['Model'] = model_name
            df['Phase'] = phase
            df['Date'] = date_folder
            all_system.append(df)
            
        # Process Physical Logs
        for file in physical_files:
            try:
                df = pd.read_csv(file)
                # Safeguard: Remove repeated header rows if the Tapo script restarted
                df = df[df['Time'] != 'Time']
                df['Watts'] = pd.to_numeric(df['Watts'], errors='coerce')
                
                basename = os.path.basename(file)
                model_name = "_".join(basename.split("_")[:-2])
                phase = "Warm-up" if "warmup_logs" in file else "Deep Aging" if "deep_aging" in file else "Uncategorized (Flat)"
                
                df['Model'] = model_name
                df['Phase'] = phase
                df['Date'] = date_folder
                all_physical.append(df)
            except Exception as e:
                pass

    df_inf = pd.concat(all_inference, ignore_index=True) if all_inference else pd.DataFrame()
    df_sys = pd.concat(all_system, ignore_index=True) if all_system else pd.DataFrame()
    df_phy = pd.concat(all_physical, ignore_index=True) if all_physical else pd.DataFrame()
    
    return df_inf, df_sys, df_phy

# --- Main Logic ---
if selected_dates:
    df_inf, df_sys, df_phy = load_research_data(selected_dates)
    
    st.subheader(f"📊 Telemetry Loaded for: {', '.join(selected_dates)}")
    
    if not df_inf.empty:
        # Dynamically validate default options
        unique_phases = df_inf['Phase'].unique().tolist()
        desired_defaults = ["Deep Aging", "Uncategorized (Flat)"]
        valid_defaults = [p for p in desired_defaults if p in unique_phases]
        
        if not valid_defaults:
            valid_defaults = unique_phases
            
        selected_phases = st.multiselect(
            "Select Execution Phase", 
            options=unique_phases, 
            default=valid_defaults
        )
        
        # Apply filters
        filtered_inf = df_inf[df_inf['Phase'].isin(selected_phases)]
        filtered_sys = df_sys[df_sys['Phase'].isin(selected_phases)] if not df_sys.empty else df_sys
        filtered_phy = df_phy[df_phy['Phase'].isin(selected_phases)] if not df_phy.empty else df_phy
        
        # ======================================================================
        # RESTORED GRAPHICS & PLOTLY CHARTS (UPDATED FOR STREAMLIT 2026)
        # ======================================================================
        st.write("### 🚀 Software Aging: Inference Throughput (TPS)")
        fig_inf = px.line(filtered_inf, x="Time", y="TPS", color="Model", facet_row="Date", 
                          title="Tokens-Per-Second Decay Over Time", template="plotly_white")
        st.plotly_chart(fig_inf, width="stretch")
        
        if not filtered_sys.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.write("### 🔥 Hardware State: CPU Package Temp")
                fig_temp = px.line(filtered_sys, x="Time", y="Temp", color="Model", facet_row="Date", 
                                   title="Thermal Saturation (°C)", template="plotly_white")
                st.plotly_chart(fig_temp, width="stretch")
                
            with col2:
                st.write("### 🧠 Software State: Memory Bloat")
                fig_ram = px.line(filtered_sys, x="Time", y="RAM_MB", color="Model", facet_row="Date", 
                                  title="KV-Cache Fragmentation (MB)", template="plotly_white")
                st.plotly_chart(fig_ram, width="stretch")
                
        if not filtered_phy.empty:
            st.write("### ⚡ Physical Power Leakage")
            fig_phy = px.line(filtered_phy, x="Time", y="Watts", color="Model", facet_row="Date", 
                              title="Absolute Wall Power (Tapo P115)", template="plotly_white")
            st.plotly_chart(fig_phy, width="stretch")
            
    else:
        st.warning("No inference data found.")
else:
    st.warning("Please select at least one experiment folder from the sidebar.")