import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. Your REAL Dashboard Data (Immediate Onset)
data = {
    'Time': ['10 Min', '30 Min', '60 Min', '120 Min'],
    'Corr_TPS': [-0.631, -0.615, -0.583, -0.523],
    'Corr_Leakage': [0.520, 0.594, 0.580, 0.501]
}
df = pd.DataFrame(data)

# 2. IEEE Formatting
layout_update = dict(
    font_family="Times New Roman",
    font_size=14,
    paper_bgcolor='white',
    plot_bgcolor='white',
    margin=dict(l=60, r=20, t=50, b=50),
    xaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black', title='Inference Duration'),
    yaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray', zerolinecolor='Black', title='Pearson Correlation (r)')
)

# 3. Create the Chart
fig_corr = go.Figure()

# Plot the two metrics
fig_corr.add_trace(go.Scatter(x=df['Time'], y=df['Corr_TPS'], mode='lines+markers', name='Temp vs TPS (Aging)', line=dict(color='blue', width=3), marker=dict(size=10)))
fig_corr.add_trace(go.Scatter(x=df['Time'], y=df['Corr_Leakage'], mode='lines+markers', name='Temp vs Leakage', line=dict(color='red', width=3), marker=dict(size=10, symbol='square')))

fig_corr.update_layout(title="Immediate Onset of Thermal Degradation", **layout_update)

# 4. Export as PDF for LaTeX
fig_corr.write_image("export_temporal_correlations.pdf", scale=3)
print("✅ Success! export_temporal_correlations.pdf generated.")