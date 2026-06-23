import pandas as pd

# Array of model names for which you want to perform the analysis
model_names = ['llama3.1_8b', 'deepseek-v2_lite', 'qwen2.5_0.5b', 'phi3_mini']

# Iterate over each model name
for model_name in model_names:
    # Your analysis code here
    print(f"Processing model: {model_name}")
    # 1. Load the datasets
    df_inf = pd.read_csv(f'{model_name}_48.00h_inference.csv')
    df_phys = pd.read_csv(f'{model_name}_48.00h_physical.csv')

    # Ensure timestamps are sorted for accurate temporal merging
    df_inf = df_inf.sort_values('timestamp').reset_index(drop=True)
    df_phys = df_phys.sort_values('timestamp').reset_index(drop=True)

    # Fill missing power_w values using the next available record
    df_phys['power_w'] = df_phys['power_w'].bfill()

    # 2. Map each physical record to the inference period it belongs to
    # For each physical timestamp, find which inference period it belongs to (backward merge)
    df_phys['inf_timestamp'] = pd.merge_asof(
        df_phys[['timestamp']], 
        df_inf[['timestamp']].rename(columns={'timestamp': 'inf_timestamp'}), 
        left_on='timestamp',
        right_on='inf_timestamp',
        direction='backward'
    )['inf_timestamp'].values

    # 3. Calculate Watts mean for each inference timestamp window
    watts_mean = df_phys.groupby('inf_timestamp')['power_w'].mean().reset_index()
    watts_mean.columns = ['timestamp', 'watts_mean']

    # 4. Merge back into the main inference dataframe
    merged_df = pd.merge(df_inf, watts_mean, on='timestamp', how='left')

    # Calculate duration between consecutive inferences (in seconds)
    # Shift up so each row has the duration until the next inference
    merged_df['inference_duration_s'] = merged_df['timestamp'].diff().shift(-1)

    # Fill the last row with the previous duration value
    merged_df['inference_duration_s'] = merged_df['inference_duration_s'].bfill()

    # Estimate prefill_dur_s and decode_dur_s based on TPS ratio
    # The inference_duration_s represents the total time, split proportionally between prefill and decode
    total_tps = merged_df['prefill_tps'] + merged_df['decode_tps']
    merged_df['prefill_dur_s'] = merged_df['inference_duration_s'] * (merged_df['prefill_tps'] / total_tps)
    merged_df['decode_dur_s'] = merged_df['inference_duration_s'] * (merged_df['decode_tps'] / total_tps)

    # 5. Compute the new metrics
    # Tokens-per-Joule
    merged_df['tokens_per_joule'] = merged_df['decode_tps'] / merged_df['watts_mean']

    # Carbon-Aware Eco-Efficiency (Tokens / gCO2eq)
    # Using 400 gCO2/kWh as a standard placeholder for CI_grid
    CI_grid = 400 
    merged_df['eco_efficiency_ce'] = (merged_df['tokens_per_joule'] * 3.6e6) / CI_grid

    # Response time (latency per token in seconds)
    merged_df['response_time_s'] = (merged_df['prefill_dur_s'] + merged_df['decode_dur_s'])

    # 6. Export the finalized dataset
    merged_df.to_csv(f'{model_name}_48.00h_merged_analysis.csv', index=False)

    # Preview the calculated columns
    print(merged_df[['timestamp', 'decode_tps', 'watts_mean', 'tokens_per_joule', 'eco_efficiency_ce', 'response_time_s', 'prefill_dur_s', 'decode_dur_s']].head())
