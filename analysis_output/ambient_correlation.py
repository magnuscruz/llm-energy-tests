"""Reconstruct ambient temperature over the campaign period and test how much
of the between-campaign CPU temperature variation it explains.

The measurement campaigns span roughly three months without an ambient sensor
(a limitation stated in the paper's Threats to Validity section). No indoor
record exists, so we reconstruct the *outdoor* hourly series from the ERA5
reanalysis via the Open-Meteo archive API and use it as a covariate.

This bounds the confound; it does not remove it. Outdoor temperature relates to
the machine room's temperature with a lag, a damping factor and an offset that
depend on the building's HVAC, solar exposure and thermal mass, none of which we
observe. The reanalysis grid cell is also ~9 km wide, so it describes the region
rather than the site.

Fetched once and cached to ambient_coimbra.csv so the analysis is reproducible
offline.
"""
import json
import os
import urllib.request

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE = os.path.join(REPO, "analysis_output", "ambient_coimbra.csv")

# University of Coimbra, Polo II (Departamento de Engenharia Informatica).
LAT, LON = 40.1863, -8.4156
START, END = "2026-05-01", "2026-08-05"

CAMPAIGNS = {
    "R1 (llama/deepseek)": "2026-05-01_48h_R1_no_throtting",
    "R1 (qwen/phi3)":      "2026-05-05_48h_R1_no_throtting",
    "R2":                  "2026-05-09_48h_R2_no_throtting",
    "87.5%":               "2026-05-20_48h_87_5_throttling",
    "75%":                 "2026-06-14_48h_75_throttling",
    "62.5% original":      "2026-07-02_48h_62_5_throttling",
    "50% hardened":        "2026-07-19_48h_50_throttling",
    "62.5% replication":   "2026-07-27_48h_62_5_throttling",
}
MODELS = ["llama3.1_8b", "deepseek-v2_lite", "qwen2.5_0.5b", "phi3_mini"]


def fetch_ambient():
    if os.path.exists(CACHE):
        print(f"using cached {CACHE}")
        return pd.read_csv(CACHE)
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={LAT}"
           f"&longitude={LON}&start_date={START}&end_date={END}"
           f"&hourly=temperature_2m&timezone=UTC")
    print(f"fetching {url}")
    with urllib.request.urlopen(url, timeout=60) as r:
        payload = json.load(r)
    df = pd.DataFrame({
        "time": payload["hourly"]["time"],
        "ambient_c": payload["hourly"]["temperature_2m"],
    })
    # Epoch seconds, computed per-value rather than by casting the column.
    # pandas 2.x infers the datetime64 resolution from the input string, and
    # for "2026-05-01T00:00" it chooses microseconds, so an int64 cast followed
    # by //10**9 silently divides the epoch by a further 1000.
    df["timestamp"] = pd.to_datetime(df.time, utc=True).map(
        lambda x: int(x.timestamp()))
    df.attrs["resolved"] = (payload.get("latitude"), payload.get("longitude"),
                            payload.get("elevation"))
    print(f"resolved grid cell: {payload.get('latitude')}, "
          f"{payload.get('longitude')} at {payload.get('elevation')} m")
    df.to_csv(CACHE, index=False)
    return df


def campaign_rows(folder):
    """Concatenate every model's fused records for one campaign."""
    frames = []
    for m in MODELS:
        p = os.path.join(REPO, "logs", folder, "deep_aging",
                         f"{m}_48.00h_merged_analysis.csv")
        if os.path.exists(p):
            d = pd.read_csv(p, low_memory=False)[["timestamp", "cpu_temp"]]
            d["model"] = m
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else None


def main():
    amb = fetch_ambient()
    print(f"ambient: {len(amb)} hourly values, "
          f"{amb.ambient_c.min():.1f} to {amb.ambient_c.max():.1f} degC\n")

    amb = amb.sort_values("timestamp")
    rows = []
    for label, folder in CAMPAIGNS.items():
        d = campaign_rows(folder)
        if d is None:
            print(f"  {label:22s} SKIP (no fused records)")
            continue
        d = d.dropna(subset=["timestamp", "cpu_temp"]).sort_values("timestamp")
        j = pd.merge_asof(d, amb[["timestamp", "ambient_c"]],
                          on="timestamp", direction="nearest")
        rows.append({
            "campaign": label,
            "n": len(j),
            "ambient_mean": j.ambient_c.mean(),
            "cpu_mean": j.cpu_temp.mean(),
            "r": j.ambient_c.corr(j.cpu_temp),
        })

    t = pd.DataFrame(rows)
    print(f"{'campaign':>22} {'n':>7} {'ambient':>9} {'cpu_temp':>9} {'r':>7}")
    for _, x in t.iterrows():
        print(f"{x.campaign:>22} {x.n:>7.0f} {x.ambient_mean:>8.1f}C "
              f"{x.cpu_mean:>8.1f}C {x.r:>7.2f}")

    print("\n=== between-campaign: does ambient explain the CPU offset? ===")
    a = t[t.campaign == "62.5% original"].iloc[0]
    b = t[t.campaign == "62.5% replication"].iloc[0]
    d_amb = b.ambient_mean - a.ambient_mean
    d_cpu = b.cpu_mean - a.cpu_mean
    print(f"  62.5% original    ambient {a.ambient_mean:5.1f}C   cpu {a.cpu_mean:5.1f}C")
    print(f"  62.5% replication ambient {b.ambient_mean:5.1f}C   cpu {b.cpu_mean:5.1f}C")
    print(f"  delta             ambient {d_amb:+5.1f}C   cpu {d_cpu:+5.1f}C")
    if d_amb:
        print(f"  cpu shift per degC of ambient shift: {d_cpu / d_amb:.2f}")

    print("\n=== across all campaigns ===")
    r = np.corrcoef(t.ambient_mean, t.cpu_mean)[0, 1]
    slope = np.polyfit(t.ambient_mean, t.cpu_mean, 1)[0]
    print(f"  correlation of campaign-mean ambient vs campaign-mean cpu_temp: r={r:.2f}")
    print(f"  slope: {slope:.2f} degC of CPU per degC of ambient")
    print("  NOTE: campaign means confound ambient with frequency cap, which is"
          " the dominant driver of cpu_temp. Interpret only within a shelf.")


if __name__ == "__main__":
    main()
