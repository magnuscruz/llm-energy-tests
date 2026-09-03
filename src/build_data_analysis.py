import glob
import os

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

    # Preserve CPU frequency telemetry for downstream analysis
    if 'scaling_cur_freq' in merged_df.columns:
        merged_df['scaling_cur_freq'] = pd.to_numeric(merged_df['scaling_cur_freq'], errors='coerce')

    # 4b. Merge offline CPU frequency samples collected at 1Hz
    freq_candidates = sorted(
        glob.glob(f'*{model_name}*_freq.csv'),
        key=os.path.getmtime,
    )
    if freq_candidates:
        df_freq = pd.read_csv(freq_candidates[-1])
        df_freq = df_freq.sort_values('timestamp').reset_index(drop=True)
        for col in ['timestamp', 'freq_khz_max', 'freq_khz_mean']:
            if col in df_freq.columns:
                df_freq[col] = pd.to_numeric(df_freq[col], errors='coerce')

        df_freq['inf_timestamp'] = pd.merge_asof(
            df_freq[['timestamp']],
            merged_df[['timestamp']].rename(columns={'timestamp': 'inf_timestamp'}),
            left_on='timestamp',
            right_on='inf_timestamp',
            direction='backward'
        )['inf_timestamp'].values

        freq_summary = df_freq.groupby('inf_timestamp')[['freq_khz_max', 'freq_khz_mean']].mean().reset_index()
        freq_summary.columns = ['timestamp', 'freq_khz_max_mean', 'freq_khz_mean_mean']
        merged_df = pd.merge(merged_df, freq_summary, on='timestamp', how='left')

    # 4c. Merge ambient temperature and humidity, if the room was instrumented.
    #
    # Unlike power and frequency, ambient is logged once for the whole campaign
    # rather than per model: a single sensor watches the room while the models
    # run in sequence. merge_asof handles that without slicing, because it joins
    # on the timestamp -- each model's rows pick up the readings from its own
    # window automatically.
    #
    # The stream comes from a separate machine (a Pi beside the node), so it is
    # only comparable because both anchor to the UNIX epoch. Verify the clocks
    # agree before a campaign: scripts/sync_pi_clock.sh. A Pi has no RTC, and a
    # drifting clock pairs readings with the wrong inference events silently.
    ambient_files = sorted(glob.glob('*ambient*.csv'), key=os.path.getmtime)
    if ambient_files:
        df_amb = pd.read_csv(ambient_files[-1])
        df_amb = df_amb.sort_values('timestamp').reset_index(drop=True)
        for col in ['timestamp', 'ambient_c', 'humidity_pct']:
            if col in df_amb.columns:
                df_amb[col] = pd.to_numeric(df_amb[col], errors='coerce')
        df_amb = df_amb.dropna(subset=['timestamp'])

        df_amb['inf_timestamp'] = pd.merge_asof(
            df_amb[['timestamp']],
            merged_df[['timestamp']].rename(columns={'timestamp': 'inf_timestamp'}),
            left_on='timestamp',
            right_on='inf_timestamp',
            direction='backward'
        )['inf_timestamp'].values

        amb_summary = df_amb.groupby('inf_timestamp')[['ambient_c', 'humidity_pct']].mean().reset_index()
        amb_summary.columns = ['timestamp', 'ambient_c_mean', 'humidity_pct_mean']
        merged_df = pd.merge(merged_df, amb_summary, on='timestamp', how='left')

        covered = merged_df['ambient_c_mean'].notna().mean() * 100
        print(f"  ambient: {ambient_files[-1]} -> {covered:.1f}% of inference events covered")
    else:
        print("  ambient: no *ambient*.csv in this directory; skipping")

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
    print(merged_df[['timestamp', 'decode_tps', 'watts_mean', 'scaling_cur_freq', 'freq_khz_max_mean', 'freq_khz_mean_mean', 'tokens_per_joule', 'eco_efficiency_ce', 'response_time_s', 'prefill_dur_s', 'decode_dur_s']].head())
