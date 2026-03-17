import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import glob
import os
import numpy as np
from scipy import stats

# --- Page Config & DEI Aesthetics ---
st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.sidebar.header("DEI-FCTUC Research Filters")

# --- Configuration & Sidebar ---
KWH_PRICE = st.sidebar.slider("Electricity Cost (€/kWh)", 0.10, 0.50, 0.22)
base_path = os.path.expanduser("~/git/llm-energy-tests/logs/")
available_dates = sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))], reverse=True)

if not available_dates:
    st.error(f"No log directories found in {base_path}")
    st.stop()

selected_date = st.sidebar.selectbox("Select Experiment Date", available_dates)

st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

# --- Data Loading Engine ---
@st.cache_data
def load_research_data(date_folder):
    log_dir = os.path.join(base_path, date_folder)
    energy_files = glob.glob(f"{log_dir}/energy_*.csv")
    
    all_merged_runs = []
    
    for e_file in energy_files:
        t_file = e_file.replace("energy_", "temp_")
        r_file = e_file.replace("energy_", "resp_")
        s_file = e_file.replace("energy_", "system_")
        p_file = e_file.replace("energy_", "physical_")
        
        if all(os.path.exists(f) for f in [t_file, r_file, s_file, p_file]):
            # 1. Load Raw Data (No headers in raw logs)
            df_e = pd.read_csv(e_file, names=['Time', 'Watts_RAPL'])
            df_t = pd.read_csv(t_file, names=['Time', 'Temp'])
            df_r = pd.read_csv(r_file, names=['Time', 'Latency'])
            df_s = pd.read_csv(s_file, names=['Time', 'CPU_Load', 'RAM_MB'])
            df_p = pd.read_csv(p_file, names=['Time', 'Watts_Physical'])
            
            # 2. Forced Numeric Conversion
            for df_temp in [df_e, df_t, df_r, df_s, df_p]:
                numeric_cols = df_temp.columns.drop('Time')
                for col in numeric_cols:
                    df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
            
            # 3. Merging
            m = pd.merge(df_e, df_t, on='Time')
            m = pd.merge(m, df_r, on='Time')
            m = pd.merge(m, df_s, on='Time')
            m = pd.merge(m, df_p, on='Time').dropna()
            
            # 4. Metadata Extraction
            filename = os.path.basename(e_file)
            parts = filename.split('_')
            m['Model'] = f"{parts[1]}_{parts[2]}" 
            
            # 5. Metrics
            m['Leakage_Delta'] = m['Watts_Physical'] - m['Watts_RAPL']
            # Convert Latency (seconds) to Throughput (Tokens per Second)
            m['TPS'] = 1 / m['Latency'].replace(0, np.nan)
            m['TPJ'] = m['TPS'] / m['Watts_Physical']
            
            all_merged_runs.append(m)
            
    if not all_merged_runs:
        return pd.DataFrame()

    full_df = pd.concat(all_merged_runs)
    
    # Reset cycle for each model so they all start at x=0
    full_df['Relative_Cycle'] = full_df.groupby('Model').cumcount()
    
    return full_df

def save_for_latex(fig, name):
    """IEEE Camera-Ready Export Configuration"""
    fig_export = pio.from_json(fig.to_json())
    fig_export.update_layout(
        font_family="Times New Roman", font_size=12,
        paper_bgcolor='white', plot_bgcolor='white',
        margin=dict(l=50, r=20, t=50, b=50)
    )
    fig_export.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black')
    fig_export.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black')
    
    fname = f"export_{name}.{format_choice}"
    fig_export.write_image(fname, format=format_choice, scale=dpi_choice/72)
    return fname

# --- Main Dashboard Execution ---
df = load_research_data(selected_date)

if not df.empty:
    # --- KPI Row ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg TPJ", f"{df['TPJ'].mean():.2f}", help="Tokens per Joule")
    m2.metric("Thermal Leakage (Avg)", f"{df['Leakage_Delta'].mean():.1f} W")
    m3.metric("Mean Temp", f"{df['Temp'].mean():.1f} °C")
    m4.metric("Avg TPS", f"{df['TPS'].mean():.2f} t/s")

    st.divider()

    # --- Charts ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🧪 Thermal Leakage Characterization")
        fig_leak = px.scatter(df, x='Temp', y='Leakage_Delta', color='Model', 
                             trendline="ols", labels={'Leakage_Delta': 'Physical Power Gap (W)'})
        st.plotly_chart(fig_leak, width='stretch')

    with c2:
        st.subheader("📉 Performance Decay (Software Aging)")
        # Now using Relative_Cycle so all models start at 0 on X-axis
        fig_aging = px.line(df, x='Relative_Cycle', y='TPS', color='Model',
                           labels={'Relative_Cycle': 'Inference Cycle', 'TPS': 'Tokens Per Second'})
        st.plotly_chart(fig_aging, width='stretch')

    st.subheader("🔗 Feature Correlation Matrix")
    corr_cols = ['Temp', 'TPS', 'Watts_Physical', 'Watts_RAPL', 'Leakage_Delta', 'RAM_MB']
    existing_cols = [c for c in corr_cols if c in df.columns]
    corr = df[existing_cols].corr()
    fig_corr = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r')
    st.plotly_chart(fig_corr, width='stretch')
    

    # --- Figure Export ---
    if st.sidebar.button("🎨 Generate Camera-Ready Figures"):
        with st.spinner("Processing vector graphics..."):
            try:
                f1 = save_for_latex(fig_leak, "thermal_leakage")
                f2 = save_for_latex(fig_aging, "performance_aging")
                f3 = save_for_latex(fig_corr, "correlation_matrix")
                
                st.sidebar.success("Figures ready for download.")
                for f in [f1, f2, f3]:
                    with open(f, "rb") as file:
                        st.sidebar.download_button(f"Download {f}", file, file_name=f)
            except Exception as e:
                st.sidebar.error(f"Export failed: {e}")

else:
    st.error("No valid research logs found. Please check your data directory.")