import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import plotly.io as pio
import numpy as np

# --- Page Config ---
st.set_page_config(layout="wide", page_title="FCTUC-DEI: LLM Sustainability Lab")

# Custom CSS for DEI-FCTUC Aesthetics
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border-radius: 10px; padding: 15px; border: 1px solid #30363d; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌡️ LLM Software Aging & Thermal Leakage Portal")
st.sidebar.header("DEI-FCTUC Research Filters")

# --- Configuration & Filters ---
KWH_PRICE = st.sidebar.slider("Electricity Cost (€/kWh)", 0.10, 0.50, 0.22)
base_path = os.path.expanduser("~/git/llm-energy-tests/logs/")
available_dates = sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))], reverse=True)

if not available_dates:
    st.error(f"No log directories found in {base_path}")
    st.stop()

selected_date = st.sidebar.selectbox("Select Experiment Date", available_dates)

# --- Publication Export Settings ---
st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

@st.cache_data
def load_research_data(date_folder):
    log_dir = os.path.join(base_path, date_folder)
    inference_files = glob.glob(f"{log_dir}/*_inference.csv")
    
    all_data = []
    for inf_file in inference_files:
        base_prefix = inf_file.replace("_inference.csv", "")
        rapl_file = f"{base_prefix}_energy_rapl.csv"
        sys_file = f"{base_prefix}_system.csv"
        phys_file = f"{base_prefix}_physical.csv"
        
        if all(os.path.exists(f) for f in [rapl_file, sys_file, phys_file]):
            df_inf = pd.read_csv(inf_file)
            df_rapl = pd.read_csv(rapl_file, names=['Time', 'Watts_RAPL'])
            df_sys = pd.read_csv(sys_file)
            df_phys = pd.read_csv(phys_file)
            
            m = pd.merge(df_inf, df_rapl, on='Time')
            m = pd.merge(m, df_sys, on='Time')
            m = pd.merge(m, df_phys, on='Time')
            
            m['Model'] = os.path.basename(inf_file).split('_')[0]
            # Handle column name discrepancy if 'Watts' is 'Watts_Physical' in your CSV
            p_col = 'Watts_Physical' if 'Watts_Physical' in m.columns else 'Watts'
            m['Leakage_Delta'] = m[p_col] - m['Watts_RAPL']
            m['TPJ'] = m['TPS'] / m[p_col]
            
            all_data.append(m)
            
    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data)
    # Reset index for each model group so they all start at 0 for the X-axis
    combined_df['Relative_Cycle'] = combined_df.groupby('Model').cumcount()
    
    return combined_df

def save_for_latex(fig, name):
    """Applies IEEE styling and exports vector graphics"""
    fig_export = pio.from_json(fig.to_json())
    fig_export.update_layout(
        font_family="Times New Roman",
        font_size=12,
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=50, r=20, t=50, b=50)
    )
    fig_export.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black')
    fig_export.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black')
    
    fname = f"export_{name}.{format_choice}"
    fig_export.write_image(fname, format=format_choice, scale=dpi_choice/72)
    return fname

# --- Main Logic ---
df = load_research_data(selected_date)

if not df.empty:
    # KPI Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg TPJ", f"{df['TPJ'].mean():.2f}", help="Tokens per Joule")
    m2.metric("Thermal Leakage (Avg)", f"{df['Leakage_Delta'].mean():.1f} W", delta=f"{df['Leakage_Delta'].max():.1f} W Max")
    m3.metric("Mean Temp", f"{df['Temp'].mean():.1f} °C")
    m4.metric("Avg TPS", f"{df['TPS'].mean():.2f} t/s")

    st.divider()

    # Graphs
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🧪 Thermal Leakage Characterization")
        fig_leak = px.scatter(df, x='Temp', y='Leakage_Delta', color='Model', 
                             trendline="ols", labels={'Leakage_Delta': 'Physical Power Gap (W)'})
        st.plotly_chart(fig_leak, use_container_width=True)

    with c2:
        st.subheader("📉 Performance Decay (Software Aging)")
        # Use Relative_Cycle instead of a global range index
        fig_aging = px.line(df, x='Relative_Cycle', y='TPS', color='Model',
                           labels={'Relative_Cycle': 'Cycle Index', 'TPS': 'Tokens Per Second'})
        st.plotly_chart(fig_aging, use_container_width=True)

    st.subheader("🔗 Feature Correlation")
    # Identify available numeric columns for correlation
    numeric_cols = ['Temp', 'TPS', 'Leakage_Delta', 'RAM_MB']
    # Check if 'Watts' or 'Watts_Physical' exists to avoid KeyError
    w_col = 'Watts_Physical' if 'Watts_Physical' in df.columns else 'Watts'
    if w_col in df.columns: numeric_cols.append(w_col)
    
    corr = df[numeric_cols].corr()
    fig_corr = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r')
    st.plotly_chart(fig_corr, use_container_width=True)

    # Export Logic
    if st.sidebar.button("🎨 Generate Camera-Ready Figures"):
        with st.spinner("Writing high-res files..."):
            try:
                f1 = save_for_latex(fig_leak, "thermal_leakage")
                f2 = save_for_latex(fig_aging, "performance_aging")
                f3 = save_for_latex(fig_corr, "correlation_matrix")
                
                st.sidebar.success("Figures ready for download below.")
                for f in [f1, f2, f3]:
                    with open(f, "rb") as file:
                        st.sidebar.download_button(f"Download {f}", file, file_name=f)
            except Exception as e:
                st.sidebar.error(f"Export failed. Ensure 'kaleido' is installed. Error: {e}")

else:
    st.error("No valid research logs found for this date.")