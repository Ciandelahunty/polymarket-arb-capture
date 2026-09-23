"""Analysis settings.

These values are fixed in ANALYSIS_PLAN.md. Change them only with a note in
that file's Deviations section explaining why.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROCESSED_DIR = ROOT / "processed"
OUTPUT_DIR = ROOT / "analysis" / "output"
UNIVERSE = ROOT / "universe.json"

POLL_INTERVAL_S = 2           # must match INTERVAL in collector.py
RECORDED_LEVELS = 10          # levels kept per side before the collector recorded cuts
SIZES = (1, 100, 500)         # basket sizes, in baskets

R_BASE = 0.0411               # 13-week US T-bill, coupon equivalent, 22 Sept 2026
R_SENSITIVITY = (0.0, R_BASE - 0.01, R_BASE + 0.01)
STALENESS_CUTOFF_S = 1.0
