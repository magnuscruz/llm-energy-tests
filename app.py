"""
Hugging Face Spaces entry point for LLM Energy Tests Dashboard
Streamlit automatically runs this as the main app entry point
"""
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
    .main {background-color: #f8f9fa;}
    .plot-container {border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 10px; background: white;}
</style>
""", unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.sidebar.header("DEI-FCTUC Research Filters")

# --- Configuration & Filters ---
base_path = os.path.expanduser("~/git/llm-energy-tests/logs/")
if not os.path.exists(base_path):
    st.error(f"Base path does not exist: {base_path}")
    st.stop()

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

st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

@st.cache_data
def load_and_merge_research_data(date_folders):
    all_inference = []
    all_physical = []

    for date_folder in date_folders:
        # Load 48-Hour Inference Logs (New Structure: timestamp, model, cpu_temp, ram_used_mb, prefill_tps, decode_tps)
        inf_files = glob.glob(os.path.join(base_path, date_folder, "**", "*_inference.csv"), recursive=True)
        for f in inf_files:
            try:
                df = pd.read_csv(f)
                df['date'] = date_folder
                # Convert UNIX timestamp to datetime for time-series rendering
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                all_inference.append(df)
            except Exception as e:
                st.warning(f"Failed to load {f}: {e}")

        # Load 1Hz Physical Power Logs
        phys_files = glob.glob(os.path.join(base_path, date_folder, "**", "*_physical.csv"), recursive=True)
        for f in phys_files:
            try:
                df = pd.read_csv(f)
                df['date'] = date_folder
                if 'Time' in df.columns:
                    df['Time'] = pd.to_datetime(df['Time'], unit='s')
                df['model'] = "_".join(os.path.basename(f).split("_")[:-2])
                all_physical.append(df)
            except Exception as e:
                st.warning(f"Failed to load {f}: {e}")

    # Merge into master DataFrames
    df_inf = pd.concat(all_inference, ignore_index=True) if all_inference else pd.DataFrame()
    df_phys = pd.concat(all_physical, ignore_index=True) if all_physical else pd.DataFrame()
    
    return df_inf, df_phys

# --- Main Dashboard Rendering ---
if selected_dates:
    df_inf, df_phys = load_and_merge_research_data(selected_dates)
    
    if not df_inf.empty:
        st.header("Phase-Aware Inference Pipeline & Memory Starvation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
            # Track EOS Attention Corruption / Jitter
            fig_tps = px.line(df_inf, x='timestamp', y='decode_tps', color='model', 
                              title='Decode Throughput (TPS) Resilience',
                              labels={'decode_tps': 'Decode TPS', 'timestamp': 'Time'})
            st.plotly_chart(fig_tps, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
            # Track Sawtooth Cache Bloat & MLA Mitigation
            fig_ram = px.line(df_inf, x='timestamp', y='ram_used_mb', color='model', 
                              title='Inelastic Memory Bloat (Unified RAM Bottleneck)',
                              labels={'ram_used_mb': 'System RAM (MB)', 'timestamp': 'Time'})
            st.plotly_chart(fig_ram, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        st.header("Thermal & Physical Hardware Constraints")
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
            # Track Redlining vs Thermal Breathing Room
            fig_temp = px.line(df_inf, x='timestamp', y='cpu_temp', color='model', 
                               title='CPU Thermal Accumulation (°C)',
                               labels={'cpu_temp': 'Temperature (°C)', 'timestamp': 'Time'})
            st.plotly_chart(fig_temp, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col4:
            if not df_phys.empty and 'Watts' in df_phys.columns: # Adjust 'Watts' column to match your physical log's wattage column 
                st.markdown("<div class='plot-container'>", unsafe_allow_html=True)
                fig_power = px.line(df_phys, x='Time', y='Watts', color='model', 
                                    title='1 Hz Physical Power Draw (Watts)',
                                    labels={'Watts': 'Power Draw (W)', 'Time': 'Time'})
                st.plotly_chart(fig_power, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Power consumption metric columns not detected in *_physical.csv logs.")

        st.divider()
        with st.expander("Raw Telemetry Data Preview"):
            st.dataframe(df_inf.head(100))

else:
    st.warning("Please select at least one experiment folder from the sidebar.")
