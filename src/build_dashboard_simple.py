import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

# ==============================================================================
# DEI Research Benchmark - LLM Sustainability Lab Dashboard
# BULLETPROOF FIX: Using Python unpacking to bypass formatting bugs
# ==============================================================================

st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
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
    all_system = []
    all_physical = []
    
    for date_folder in date_folders:
        log_dir = os.path.join(base_path, date_folder)
        
        inf_files = glob.glob(os.path.join(log_dir, "**", "*_inference.csv"), recursive=True)
        sys_files = glob.glob(os.path.join(log_dir, "**", "*_system.csv"), recursive=True)
        phy_files = glob.glob(os.path.join(log_dir, "**", "*_physical.csv"), recursive=True)
        
        for f in inf_files:
            df = pd.read_csv(f)
            df['Model'] = "_".join(os.path.basename(f).split("_")[:-2])
            df['Phase'] = "Warm-up" if "warmup_logs" in f else "Deep Aging" if "deep_aging" in f else "Uncategorized (Flat)"
            df['Date'] = date_folder
            all_inference.append(df)
            
        for f in sys_files:
            df = pd.read_csv(f)
            df['Model'] = "_".join(os.path.basename(f).split("_")[:-2])
            df['Phase'] = "Warm-up" if "warmup_logs" in f else "Deep Aging" if "deep_aging" in f else "Uncategorized (Flat)"
            df['Date'] = date_folder
            all_system.append(df)
            
        for f in phy_files:
            try:
                df = pd.read_csv(f)
                df = df[df['Time'] != 'Time']
                df['Watts'] = pd.to_numeric(df['Watts'], errors='coerce')
                df['Model'] = "_".join(os.path.basename(f).split("_")[:-2])
                df['Phase'] = "Warm-up" if "warmup_logs" in f else "Deep Aging" if "deep_aging" in f else "Uncategorized (Flat)"
                df['Date'] = date_folder
                all_physical.append(df)
            except Exception:
                pass

    df_inf = pd.concat(all_inference, ignore_index=True) if all_inference else pd.DataFrame()
    df_sys = pd.concat(all_system, ignore_index=True) if all_system else pd.DataFrame()
    df_phy = pd.concat(all_physical, ignore_index=True) if all_physical else pd.DataFrame()
    
    if df_inf.empty or df_sys.empty:
        return pd.DataFrame()

    df_m = pd.merge(df_inf, df_sys, on=['Date', 'Model', 'Phase', 'Time'], how='inner')
    
    if not df_phy.empty:
        df_phy_grouped = df_phy.groupby(['Date', 'Model', 'Phase', 'Time'])['Watts'].mean().reset_index()
        df_m = pd.merge(df_m, df_phy_grouped, on=['Date', 'Model', 'Phase', 'Time'], how='left')
        df_m['Watts'] = df_m.groupby(['Date', 'Model', 'Phase'])['Watts'].ffill().bfill()
        
        df_m['TPJ'] = df_m['TPS'] / df_m['Watts']
        df_m['Leakage_Delta'] = df_m['Watts'] - df_m.groupby(['Date', 'Model', 'Phase'])['Watts'].transform('min')
    else:
        df_m['Watts'] = None
        df_m['TPJ'] = None
        df_m['Leakage_Delta'] = None

    df_m['Cycle Index'] = df_m.groupby(['Date', 'Model', 'Phase']).cumcount()
    return df_m

# --- Main Dashboard Rendering ---
if selected_dates:
    df_merged = load_and_merge_research_data(selected_dates)
    
    if not df_merged.empty:
        unique_phases = df_merged['Phase'].unique().tolist()
        valid_defaults = [p for p in ["Deep Aging", "Uncategorized (Flat)"] if p in unique_phases]
        if not valid_defaults:
            valid_defaults = unique_phases
            
        selected_phases = st.multiselect("Select Execution Phase", options=unique_phases, default=valid_defaults)
        df_filtered = df_merged[df_merged['Phase'].isin(selected_phases)]

        st.divider()

        st.subheader("🚀 Software Aging Decay")
        fig_inf = px.line(df_filtered, x="Cycle Index", y="TPS", color="Model", facet_row="Date", 
                          title="Tokens Per Second Over Continuous Operations", template="plotly_white")
        st.plotly_chart(fig_inf, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔥 CPU Package Temp")
            fig_temp = px.line(df_filtered, x="Cycle Index", y="Temp", color="Model", facet_row="Date", 
                               title="Thermal Saturation (°C) Over Cycles", template="plotly_white")
            st.plotly_chart(fig_temp, width="stretch")
            
        with col2:
            st.subheader("🧠 Memory Bloat")
            fig_ram = px.line(df_filtered, x="Cycle Index", y="RAM_MB", color="Model", facet_row="Date", 
                              title="KV-Cache Fragmentation (MB) Over Cycles", template="plotly_white")
            st.plotly_chart(fig_ram, width="stretch")

        if not df_filtered['Watts'].isna().all():
            st.subheader("⚡ Physical Power Leakage")
            fig_phy = px.line(df_filtered, x="Cycle Index", y="Watts", color="Model", facet_row="Date", 
                              title="Absolute Wall Power (W) Over Cycles", template="plotly_white")
            st.plotly_chart(fig_phy, width="stretch")

        st.divider()

        col3, col4 = st.columns(2)
        with col3:
            st.subheader("🔥 Thermal Hardware Overload")
            if not df_filtered['Watts'].isna().all():
                fig_scatter = px.scatter(df_filtered, x="Temp", y="Watts", color="Model", 
                                         trendline="ols", labels={"Watts": "Physical Power Gap (W)", "Temp": "Package Temp (°C)"},
                                         title="Sustained Thermal Leakage Correlation", template="plotly_white")
                st.plotly_chart(fig_scatter, width="stretch")

        with col4:
            st.subheader("🧠 System Variable Correlation")
            cols_corr = ['Temp', 'TPS', 'Leakage_Delta', 'RAM_MB', 'Watts']
            valid_cols = [c for c in cols_corr if c in df_filtered.columns and not df_filtered[c].isna().all()]
            
            if valid_cols:
                corr_matrix = df_filtered[valid_cols].corr()
                fig_corr = px.imshow(corr_matrix, text_auto=".6f", aspect="auto", color_continuous_scale="RdBu_r", 
                                     title="System-Wide Degradation Map")
                st.plotly_chart(fig_corr, width="stretch")

        if len(selected_dates) == 2:
            st.divider()
            st.subheader("📊 Comparative Efficiency Analysis")
            
            # ==================================================================
            # THE BULLETPROOF FIX: Python Unpacking (No brackets needed!)
            # ==================================================================
            date_target, date_base = selected_dates
            
            means = df_filtered.groupby(['Date', 'Model'])[['TPS', 'Watts', 'TPJ']].mean().reset_index()
            base_df = means[means['Date'] == date_base].set_index('Model')
            target_df = means[means['Date'] == date_target].set_index('Model')
            
            comp = target_df.join(base_df, lsuffix='_tgt', rsuffix='_base').dropna()
            comp['TPS Change (%)'] = (comp['TPS_tgt'] - comp['TPS_base']) / comp['TPS_base'] * 100
            comp['Energy Change (%)'] = (comp['Watts_tgt'] - comp['Watts_base']) / comp['Watts_base'] * 100
            comp['Efficiency (TPJ) Change (%)'] = (comp['TPJ_tgt'] - comp['TPJ_base']) / comp['TPJ_base'] * 100
            
            comp_melt = comp[['TPS Change (%)', 'Energy Change (%)', 'Efficiency (TPJ) Change (%)']].reset_index().melt(
                id_vars='Model', var_name='Metric', value_name='Change (%)'
            )
            
            fig_bar = px.bar(comp_melt, x='Model', y='Change (%)', color='Metric', barmode='group',
                             title=f"Efficiency Impact: {date_target} vs Baseline ({date_base})",
                             template="plotly_white", labels={"Model": "Edge AI Model"})
            
            fig_bar.update_traces(texttemplate='%{y:+.1f}%', textposition='outside')
            fig_bar.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
            st.plotly_chart(fig_bar, width="stretch")

    else:
        st.warning("No valid overlapping telemetry data found to merge.")
else:
    st.warning("Please select at least one experiment folder from the sidebar.")