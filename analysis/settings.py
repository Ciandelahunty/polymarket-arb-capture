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

# US Treasury bill yields on 22 Sept 2026, coupon-equivalent basis, as
# (maturity in years, yield). Used for the horizon-matched robustness check:
# each snapshot is discounted at the yield for its time to resolution,
# interpolated linearly and held flat beyond the shortest and longest bills.
TREASURY_CURVE = (
    (4 / 52, 0.0388), (6 / 52, 0.0394), (8 / 52, 0.0399), (13 / 52, 0.0411),
    (17 / 52, 0.0418), (26 / 52, 0.0430), (52 / 52, 0.0440),
)
STALENESS_CUTOFF_S = 1.0

# Holding rewards: Polymarket pays an annual reward on positions held in markets
# it selects. For events listed here, the buy-side discount rate is reduced by
# the reward rate, since holding the basket earns it. Empty = no adjustment.
HOLDING_REWARD_RATE = 0.0325      # Polymarket Help Center, checked 24 Sept 2026
HOLDING_REWARD_EVENTS = {"balance-of-power-2026-midterms"}
MAX_STEP_S = 12.0             # snapshots further apart than this have missing data between them
