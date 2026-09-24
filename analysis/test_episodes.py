"""Tests for violation episodes. Run with: pytest analysis"""
import math

import pandas as pd
import pytest

from episodes import N, U, V, episodes_for, find_episodes


def run(states, ticks=None, gaps=None):
    ticks = ticks if ticks is not None else [2.0 * i for i in range(len(states))]
    gaps = gaps if gaps is not None else [-0.01 if s == V else 0.05 for s in states]
    return find_episodes(ticks, states, gaps)


def test_no_violations_gives_no_episodes():
    assert run([N, N, N]) == []
    assert run([U, U]) == []
    assert run([]) == []


def test_closed_episode_has_both_duration_bounds():
    (ep,) = run([N, V, V, N])          # snapshots at 0, 2, 4, 6 seconds
    assert ep["n_snapshots"] == 2
    assert ep["duration_min_s"] == 2   # first to last violating snapshot
    assert ep["duration_max_s"] == 6   # clean snapshot before to clean snapshot after
    assert not ep["left_censored"] and not ep["right_censored"]
    assert not ep["interrupted"]


def test_single_snapshot_episode():
    (ep,) = run([N, V, N])
    assert ep["duration_min_s"] == 0
    assert ep["duration_max_s"] == 4


def test_episode_at_start_of_data_is_left_censored():
    (ep,) = run([V, V, N])
    assert ep["left_censored"] and not ep["right_censored"]
    assert math.isnan(ep["duration_max_s"])


def test_episode_at_end_of_data_is_right_censored():
    (ep,) = run([N, V, V])
    assert ep["right_censored"] and not ep["left_censored"]


def test_unknown_inside_an_episode_does_not_split_it():
    (ep,) = run([N, V, U, V, N])
    assert ep["n_snapshots"] == 2
    assert ep["interrupted"]
    assert ep["duration_min_s"] == 4   # violating snapshots at 2 s and 6 s


def test_unknown_just_before_or_after_censors_the_episode():
    (ep,) = run([N, U, V, N])
    assert ep["left_censored"] and not ep["right_censored"]
    (ep,) = run([N, V, U, N])
    assert ep["right_censored"] and not ep["left_censored"]


def test_time_gap_counts_as_missing_data():
    # 30 seconds between snapshots is longer than MAX_STEP_S.
    (ep,) = run([N, V, V, N], ticks=[0.0, 2.0, 32.0, 34.0])
    assert ep["interrupted"]
    (ep,) = run([N, V, N], ticks=[0.0, 30.0, 32.0])
    assert ep["left_censored"]


def test_clean_snapshot_separates_episodes():
    eps = run([N, V, N, V, N])
    assert len(eps) == 2


def test_min_gap_is_the_deepest_point():
    (ep,) = run([N, V, V, V, N], gaps=[0.05, -0.01, -0.04, -0.02, 0.05])
    assert ep["min_gap"] == pytest.approx(-0.04)


# --- From processed rows -------------------------------------------------

def rows(prices, status="ok", t_years=0.5, window=0.1):
    """Processed-table rows for one event on the sell side at size 1."""
    return pd.DataFrame({
        "tick": [2.0 * i for i in range(len(prices))],
        "event": "e",
        "t_years": t_years,
        "window_s": window,
        "sell_status_1": status,
        "sell_price_1": prices,
        "sell_fees_1": 0.0,
    })


def test_sell_violation_found_from_rows():
    ep = episodes_for(rows([0.98, 1.02, 1.03, 0.99]), "sell", 1)
    assert len(ep) == 1
    assert ep.loc[0, "n_snapshots"] == 2
    assert ep.loc[0, "min_gap"] == pytest.approx(-0.03)


def test_unpriceable_rows_are_unknown():
    df = rows([0.98, 1.02, 1.03, 0.99])
    df.loc[2, "sell_status_1"] = "truncated"
    df.loc[2, "sell_price_1"] = None
    ep = episodes_for(df, "sell", 1)
    assert ep.loc[0, "n_snapshots"] == 1
    assert ep.loc[0, "right_censored"]


def test_staleness_filter_makes_slow_rows_unknown():
    df = rows([0.98, 1.02, 0.99])
    df.loc[1, "window_s"] = 2.5
    assert len(episodes_for(df, "sell", 1)) == 1
    assert len(episodes_for(df, "sell", 1, staleness_cutoff=1.0)) == 0


def test_rows_at_or_past_end_date_are_unknown():
    df = rows([0.98, 1.02, 0.99], t_years=0.0)
    assert len(episodes_for(df, "sell", 1)) == 0


def test_buy_gap_is_discounted():
    df = pd.DataFrame({"tick": [0.0, 2.0, 4.0], "event": "e", "t_years": 1.0,
                       "window_s": 0.1, "buy_status_1": "ok",
                       "buy_price_1": [0.99, 0.95, 0.99], "buy_fees_1": 0.0})
    # At r = 4%, the discounted $1 is 0.9615: only 0.95 is below it.
    ep = episodes_for(df, "buy", 1, r=0.04)
    assert len(ep) == 1
    assert ep.loc[0, "min_gap"] == pytest.approx(0.95 - 1 / 1.04)
