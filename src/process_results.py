import pandas as pd
import glob
import os

# Path to your LVM logs
log_path = os.path.expanduser("~/git/llm-energy-tests/logs/*.csv")
files = glob.glob(log_path)

all_data = []
for f in files:
    # Extract model name from filename: energy_llama3_8b_TIMESTAMP.csv
    model_name = os.path.basename(f).split('_')[1] 
    df = pd.read_csv(f, names=['Time', 'Watts'])
    df['Model'] = model_name
    all_data.append(df)

full_df = pd.concat(all_data)
summary = full_df.groupby('Model')['Watts'].agg(['mean', 'max', 'std']).reset_index()
print(summary)
