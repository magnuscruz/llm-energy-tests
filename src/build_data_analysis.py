import glob
import os
import re
import sys

import pandas as pd

# The model set and the duration token used to be written here as
# ['llama3.1_8b', ...] and '48.00h'. Both are properties of the directory, not
# of the fusion: the OCR boundary campaign runs one vision model in 4 h cells,
# and no campaign has ever actually been 48.00 h -- that string is the target
# the orchestrator was asked for, not what completed. So discover both from
# the files that are present.
STEM = re.compile(r'^(?P<model>.+)_(?P<dur>[0-9.]+h)_inference\.csv$')
runs = []
for path in sorted(glob.glob('*_inference.csv')):
    m = STEM.match(os.path.basename(path))
    if m:
        runs.append((m.group('model'), m.group('dur')))
if not runs:
    sys.exit("no *_inference.csv here. build_data_analysis.py uses paths "
             "relative to the working directory: cd into the campaign's "
             "deep_aging/ (or a cell's) folder first.")

for model_name, dur in runs:
    prefix = f'{model_name}_{dur}'
    print(f"Processing model: {model_name} ({dur})")
    # 1. Load the datasets
    df_inf = pd.read_csv(f'{prefix}_inference.csv')
    df_phys = pd.read_csv(f'{prefix}_physical.csv')

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
        for col in ['timestamp', 'ambient_c', 'humidity_pct']:
            if col in df_amb.columns:
                df_amb[col] = pd.to_numeric(df_amb[col], errors='coerce')
        df_amb = df_amb.dropna(subset=['timestamp'])
        # An unclean shutdown on the Pi leaves a tail of NUL bytes where the
        # last minutes should be. read_csv turns that into one NaN row, which
        # the dropna above removes -- but the column is float64 by then, and
        # merge_asof refuses to join float keys against the int64 stamps in
        # merged_df. Cast back before sorting, not after: coercing first also
        # keeps the sort numeric rather than lexicographic.
        df_amb['timestamp'] = df_amb['timestamp'].astype('int64')
        df_amb = df_amb.sort_values('timestamp').reset_index(drop=True)

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

    # prefill_dur_s and decode_dur_s arrive from the inference log as the
    # engine's own prompt_eval_duration and eval_duration. They used to be
    # OVERWRITTEN here by apportioning inference_duration_s in proportion to
    # each phase's TPS, which was wrong twice: it replaced exact numbers with
    # an estimate, and the estimate was inverted. Time per phase goes as
    # tokens/TPS, so a phase with HIGHER throughput should receive LESS of the
    # window, not more. On a typical Qwen2.5 row the engine reported prefill
    # 0.0097 s and decode 2.87 s; the apportionment wrote 2.93 s and 0.07 s.
    #
    # Nothing reported in either manuscript used these columns -- tokens per
    # joule is decode_tps/watts_mean, and response_time_s came out as the
    # window itself, because the two shares summed to one. The merged files
    # already released carry the wrong split; regenerating them is a separate
    # decision, since it changes the archived artefact.
    #
    # Keeping the engine's own durations, response_time_s becomes the time the
    # engine spent on the request rather than the spacing between requests,
    # which is what the name claims.

    # 5. Compute the new metrics
    # Tokens-per-Joule
    merged_df['tokens_per_joule'] = merged_df['decode_tps'] / merged_df['watts_mean']

    # Carbon-Aware Eco-Efficiency (Tokens / gCO2eq)
    # Using 400 gCO2/kWh as a standard placeholder for CI_grid
    CI_grid = 400 
    merged_df['eco_efficiency_ce'] = (merged_df['tokens_per_joule'] * 3.6e6) / CI_grid

    # End-to-end engine time for the request: prefill plus decode, as reported
    # by the engine. inference_duration_s remains the wall-clock spacing
    # between consecutive events, which is the longer quantity.
    merged_df['response_time_s'] = (merged_df['prefill_dur_s'] + merged_df['decode_dur_s'])

    # 6. Export the finalized dataset
    merged_df.to_csv(f'{prefix}_merged_analysis.csv', index=False)

    # Preview the calculated columns
    print(merged_df[['timestamp', 'decode_tps', 'watts_mean', 'scaling_cur_freq', 'freq_khz_max_mean', 'freq_khz_mean_mean', 'tokens_per_joule', 'eco_efficiency_ce', 'response_time_s', 'prefill_dur_s', 'decode_dur_s']].head())
