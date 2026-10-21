import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_threats_figure import MODEL_STYLE, prefill_mean, R1_DIR, INVALID_50_DIR, VALID_DIRS, NOMINAL_50_MHZ

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
VERIFIED_50_DIR = f"{LOGS_DIR}/2026-07-19_48h_50_throttling/deep_aging"

xs_4 = np.array([mhz for _, mhz in VALID_DIRS.values()], dtype=float)

for m, style in MODEL_STYLE.items():
    r1 = prefill_mean(R1_DIR, m)
    ys_4 = np.array([prefill_mean(d, m) / r1 for d, _ in VALID_DIRS.values()])
    slope_4, intercept_4 = np.polyfit(xs_4, ys_4, 1)
    exp_4 = slope_4 * NOMINAL_50_MHZ + intercept_4
    
    v50 = prefill_mean(VERIFIED_50_DIR, m) / r1
    inv50 = prefill_mean(INVALID_50_DIR, m) / r1
    
    xs_5 = np.array([NOMINAL_50_MHZ] + list(xs_4))
    ys_5 = np.array([v50] + list(ys_4))
    slope_5, intercept_5 = np.polyfit(xs_5, ys_5, 1)
    
    corr_4 = np.corrcoef(xs_4, ys_4)[0, 1]**2
    corr_5 = np.corrcoef(xs_5, ys_5)[0, 1]**2
    
    print(f"{style['label']:18s}:")
    print(f"  4-pt fit (62.5-100%): R2={corr_4:.4f}, expected@1750={exp_4:.3f}")
    print(f"  Verified 50% (sem turbo): {v50:.3f}")
    print(f"  Original 50% (com turbo): {inv50:.3f}")
    print(f"  5-pt fit (50-100%):   R2={corr_5:.4f}")
