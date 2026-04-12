import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os
import plotly.io as pio
import numpy as np

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

### --- Publication Export Settings ---
st.sidebar.divider()
st.sidebar.subheader("📤 IEEE Publication Export")
format_choice = st.sidebar.selectbox("Vector/Raster Format", ["pdf", "svg", "eps", "png"])
dpi_choice = st.sidebar.slider("Resolution (DPI)", 150, 600, 300)

@st.cache_data
def load_research_data(date_folders):
    all_dfs = []
    for date_folder in date_folders:
        log_dir = os.path.join(base_path, date_folder)
        inference_files = glob.glob(f"{log_dir}/*_inference.csv")
        
        for inf_file in inference_files:
            # 1. Read Inference
            df_inf = pd.read_csv(inf_file)
            
            # 2. Read and Merge System Data (Temp, RAM_MB)
            sys_file = inf_file.replace('_inference.csv', '_system.csv')
            if os.path.exists(sys_file):
                df_sys = pd.read_csv(sys_file)
                df_temp = pd.merge(df_inf, df_sys, on='Time', how='inner')
            else:
                df_temp = df_inf
                
            # 3. Read and Merge Physical Data (Watts)
            phys_file = inf_file.replace('_inference.csv', '_physical.csv')
            if os.path.exists(phys_file):
                df_phys = pd.read_csv(phys_file)
                df_temp = pd.merge(df_temp, df_phys, on='Time', how='inner')
            
            df_temp['Experiment_Folder'] = date_folder
            
            if 'Model' not in df_temp.columns:
                base_name = os.path.basename(inf_file).replace('_inference.csv', '')
                parts = base_name.split('_')
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
        st.sidebar.divider()
        st.sidebar.subheader("Select Models")
        
        available_models = sorted(df['Model'].unique())
        selected_models = []
        
        for model in available_models:
            if st.sidebar.checkbox(model, value=True):
                selected_models.append(model)
                
        filtered_df = df[df['Model'].isin(selected_models)]
        
        if filtered_df.empty:
            st.warning("Please select at least one model from the sidebar to view data.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            if 'TPJ' in filtered_df.columns:
                m1.metric("Avg TPJ", f"{filtered_df['TPJ'].mean():.2f}", help="Tokens per Joule")
            else:
                m1.metric("Avg TPJ", "N/A")
                
            if 'Watts' in filtered_df.columns:
                m2.metric("Physical Power (Avg)", f"{filtered_df['Watts'].mean():.1f} W", delta=f"{filtered_df['Watts'].max():.1f} W Max", delta_color="inverse")
            elif 'Leakage_Delta' in filtered_df.columns:
                m2.metric("Thermal Leakage", f"{filtered_df['Leakage_Delta'].mean():.1f} W")
            else:
                m2.metric("Physical Power", "N/A")
                
            if 'Temp' in filtered_df.columns:
                m3.metric("Mean Temp", f"{filtered_df['Temp'].mean():.1f} °C")
            if 'TPS' in filtered_df.columns:
                m4.metric("Avg TPS", f"{filtered_df['TPS'].mean():.2f} t/s")
            
            st.divider()

            ### --- CLUSTER STATS & PERCENTILES ---
            st.subheader("📊 Cluster Performance & Percentile Analysis")
            st.markdown("Calculates the central tendency (mean) and performance spread (95th - 5th percentile) to identify extreme instability caused by thermal saturation and software aging.")

            agg_dict = {}
            if 'TPS' in filtered_df.columns:
                agg_dict['TPS_Mean'] = ('TPS', 'mean')
                agg_dict['TPS_5th'] = ('TPS', lambda x: x.quantile(0.05))
                agg_dict['TPS_95th'] = ('TPS', lambda x: x.quantile(0.95))
            if 'Temp' in filtered_df.columns:
                agg_dict['Temp_Mean'] = ('Temp', 'mean')
                agg_dict['Temp_5th'] = ('Temp', lambda x: x.quantile(0.05))
                agg_dict['Temp_95th'] = ('Temp', lambda x: x.quantile(0.95))
            if 'RAM_MB' in filtered_df.columns:
                agg_dict['RAM_Mean'] = ('RAM_MB', 'mean')
                agg_dict['RAM_Max_Bloat'] = ('RAM_MB', lambda x: x.quantile(0.99)) 
            if 'Watts' in filtered_df.columns:
                agg_dict['Watts_Mean'] = ('Watts', 'mean')
                
            if agg_dict:
                cluster_stats = filtered_df.groupby(['Model', 'Experiment_Folder']).agg(**agg_dict).reset_index()

                if 'TPS' in filtered_df.columns:
                    cluster_stats['TPS_Diff (95th-5th)'] = cluster_stats['TPS_95th'] - cluster_stats['TPS_5th']
                if 'Temp' in filtered_df.columns:
                    cluster_stats['Temp_Diff (95th-5th)'] = cluster_stats['Temp_95th'] - cluster_stats['Temp_5th']

                format_dict = {}
                for col in cluster_stats.columns:
                    if 'TPS' in col: format_dict[col] = '{:.2f}'
                    elif 'Temp' in col: format_dict[col] = '{:.1f} °C'
                    elif 'RAM' in col: format_dict[col] = '{:.0f} MB'
                    elif 'Watts' in col: format_dict[col] = '{:.1f} W'

                st.dataframe(cluster_stats.style.format(format_dict), use_container_width=True)

                # --- ROW 2 VISUALIZATIONS ---
                col1, col2 = st.columns(2)
                
                with col1:
                    # Visualizing Performance Instability
                    if 'TPS_Diff (95th-5th)' in cluster_stats.columns:
                        st.markdown("#### Visualizing Performance Instability")
                        fig_spread = px.bar(
                            cluster_stats, 
                            x="Model", 
                            y="TPS_Diff (95th-5th)", 
                            color="Experiment_Folder",
                            barmode="group",
                            title="Tokens-per-Second Spread (95th - 5th Percentile)",
                            labels={"TPS_Diff (95th-5th)": "TPS Spread (Wider = More Instability)"},
                            template="plotly_dark"
                        )
                        st.plotly_chart(fig_spread, use_container_width=True)

                with col2:
                    # --- NEW: ENERGY PERFORMANCE (TPJ) IMPROVEMENT CHART ---
                    print(f"Selected Dates: {len(selected_dates)}, Watts_Mean: {'Watts_Mean' in cluster_stats.columns}, TPS_Mean: {'TPS_Mean' in cluster_stats.columns}")
                    if len(selected_dates) == 2 and 'Watts_Mean' in cluster_stats.columns and 'TPS_Mean' in cluster_stats.columns:
                        folder_A, folder_B = selected_dates[1], selected_dates[0]  # folder_B is Baseline
                        
                        # Pivot both TPS and Watts to compare Folders A and B simultaneously
                        pivot_df = cluster_stats.pivot(index='Model', columns='Experiment_Folder', values=['Watts_Mean', 'TPS_Mean'])
                        # Flatten MultiIndex Columns
                        pivot_df.columns = [f"{col[0]}_{col[1]}" for col in pivot_df.columns]
                        pivot_df = pivot_df.reset_index()
                        print(f"Pivoted DataFrame Columns: {pivot_df.columns}")
                        
                        if f'Watts_Mean_{folder_A}' in pivot_df.columns and f'Watts_Mean_{folder_B}' in pivot_df.columns:
                            # 1. Calculate Energy Change
                            pivot_df['Energy Change (%)'] = ((pivot_df[f'Watts_Mean_{folder_A}'] - pivot_df[f'Watts_Mean_{folder_B}']) / pivot_df[f'Watts_Mean_{folder_B}']) * 100
                            
                            # 2. Calculate TPS Change
                            pivot_df['TPS Change (%)'] = ((pivot_df[f'TPS_Mean_{folder_A}'] - pivot_df[f'TPS_Mean_{folder_B}']) / pivot_df[f'TPS_Mean_{folder_B}']) * 100
                            
                            # 3. Calculate Efficiency (Tokens per Joule) Change
                            tpj_A = pivot_df[f'TPS_Mean_{folder_A}'] / pivot_df[f'Watts_Mean_{folder_A}']
                            tpj_B = pivot_df[f'TPS_Mean_{folder_B}'] / pivot_df[f'Watts_Mean_{folder_B}']
                            pivot_df['Efficiency (TPJ) Change (%)'] = ((tpj_A - tpj_B) / tpj_B) * 100
                            
                            # Melt the dataframe for a grouped Plotly bar chart
                            plot_df = pivot_df.melt(
                                id_vars='Model', 
                                value_vars=['TPS Change (%)', 'Energy Change (%)', 'Efficiency (TPJ) Change (%)'], 
                                var_name='Metric', 
                                value_name='Change (%)'
                            )
                            
                            st.markdown("#### Performance Drop vs. Energy Savings")
                            fig_delta = px.bar(
                                plot_df,
                                x='Model',
                                y='Change (%)',
                                color='Metric',
                                barmode='group',
                                text=plot_df['Change (%)'].apply(lambda x: f"{x:+.1f}%"),
                                title=f"Efficiency Impact: {folder_A} vs Baseline ({folder_B})",
                                labels={'Change (%)': "Change (%)", 'Model': "Edge AI Model"},
                                template="plotly_dark",
                                color_discrete_map={
                                    'TPS Change (%)': '#636efa',             # Blue
                                    'Energy Change (%)': '#ef553b',          # Red
                                    'Efficiency (TPJ) Change (%)': '#00cc96' # Green
                                }
                            )
                            fig_delta.update_traces(textposition='outside')
                            # Expand the Y-axis slightly so labels don't clip
                            fig_delta.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
                            st.plotly_chart(fig_delta, use_container_width=True)

            st.divider()
            
            # --- ENERGY CONSUMPTION GRAPHIC ---
            if 'Watts' in filtered_df.columns:
                st.subheader("⚡ Physical Energy Consumption Distribution")
                st.markdown("Visualizes absolute hardware ground truth. Bypassing software-telemetry reveals the exponential power penalty triggered when heavy models hit their thermal ceiling.")
                
                fig_energy = px.box(
                    filtered_df,
                    x="Model",
                    y="Watts",
                    color="Experiment_Folder",
                    title="Hardware Power Draw (Watts) by Model",
                    labels={"Watts": "Absolute Power Draw (W)", "Model": "Edge AI Model"},
                    template="plotly_dark"
                )
                st.plotly_chart(fig_energy, use_container_width=True)
                st.divider()
            
            # --- THERMAL LEAKAGE DENSITY SCATTER PLOT ---
            if 'Temp' in filtered_df.columns and 'Watts' in filtered_df.columns:
                st.subheader("Comparative Analysis: Thermal Leakage (Temperature vs. Physical Power)")
                st.markdown("This density scatter plot maps the absolute physical power gap (W) against hardware temperature. It exposes the exponential physical power leakage triggered when models cross the critical thermal inflection point.")
                
                fig_scatter = px.scatter(
                    filtered_df, 
                    x="Temp", 
                    y="Watts", 
                    color="Model", 
                    symbol="Experiment_Folder",
                    title="Physical Power Gap (W) by Hardware Temperature",
                    labels={"Temp": "Hardware Temperature (°C)", "Watts": "Absolute Physical Power (W)"},
                    template="plotly_dark",
                    opacity=0.6,
                    hover_data=['Time', 'TPS', 'RAM_MB'] if 'RAM_MB' in filtered_df.columns and 'TPS' in filtered_df.columns else None
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.error("No valid research logs found for the selected dates.")
else:
    st.warning("Please select at least one experiment folder.")