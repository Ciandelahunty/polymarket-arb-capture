"""Tests for the paper-trading bot and capture rate. Run with: pytest analysis"""
import numpy as np
import pandas as pd
import pytest

from episodes import N, U, V
from results import capture_at_snapshots, paper_trades


def test_bot_trades_when_violation_persists_at_size():
    # Violation seen at 2 s; at 4 s the size-100 basket is still 1c below the bound.
    out = paper_trades([0, 2, 4, 6], [N, V, V, N], [0.05, 0.02, -0.01, 0.03], q=100)
    assert len(out) == 1
    assert out[0]["outcome"] == "traded"
    assert out[0]["pnl"] == pytest.approx(1.00)   # 1 cent x 100 baskets


def test_bot_misses_when_gone_by_next_snapshot():
    out = paper_trades([0, 2, 4], [N, V, N], [0.05, -0.02, 0.01], q=1)
    assert out[0]["outcome"] == "gone" and out[0]["pnl"] == 0


def test_bot_outcome_unknown_when_next_snapshot_missing():
    assert paper_trades([0, 2], [N, V], [0.1, -0.1], q=1)[0]["outcome"] == "unknown"
    assert paper_trades([0, 2, 40], [N, V, V], [0.1, -0.1, -0.1], q=1)[0]["outcome"] == "unknown"
    assert paper_trades([0, 2, 4], [N, V, V], [0.1, -0.1, np.nan], q=1)[0]["outcome"] == "unknown"


def test_bot_counts_one_sighting_per_run():
    out = paper_trades([0, 2, 4, 6, 8, 10], [N, V, V, V, N, V], [0] * 6, q=1)
    assert len(out) == 2


def test_capture_at_snapshots_counts():
    gap_1 = pd.Series([-0.01, -0.02, -0.01, 0.03, -0.01])
    gap_q = pd.Series([-0.005, 0.01, np.nan, -0.02, 0.02])
    c = capture_at_snapshots(gap_1, gap_q)
    assert c["visible_at_1"] == 4
    assert (c["remain"], c["gone"], c["unknown"]) == (1, 2, 1)
    assert c["capture_rate"] == pytest.approx(1 / 3)
