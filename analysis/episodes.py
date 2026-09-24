"""Violation episodes: runs of consecutive snapshots in violation.

For each event, side and size, every snapshot is classed as:
  V  in violation (gap below zero),
  N  not in violation,
  U  unknown: basket incomplete or not priceable, at or past the event's
     end date, or (optionally) above the staleness cutoff.
Snapshots further apart than MAX_STEP_S also have unknown data between them.

An episode is a run of V snapshots. Unknown data neither ends nor extends an
episode: V U V is one episode, marked as interrupted. An episode with unknown
data (or the start of collection) just before it is left-censored; one with
unknown data (or the end of collection) just after it is right-censored.

Durations are reported as bounds, since violations can start or end between
snapshots:
  duration_min_s  first to last snapshot in violation (0 for a single one)
  duration_max_s  last clean snapshot before to first clean snapshot after
                  (only when neither end is censored)

Run from the repository folder to write analysis/output/episodes.csv:
    python analysis/episodes.py
"""
import numpy as np
import pandas as pd

from costs import OK
from load import load_processed
from settings import (HOLDING_REWARD_EVENTS, HOLDING_REWARD_RATE, MAX_STEP_S,
                      OUTPUT_DIR, R_BASE, SIZES, STALENESS_CUTOFF_S)

N, V, U = 0, 1, 2

EPISODE_COLUMNS = ["event", "side", "size", "start", "end", "prev_clean", "next_clean",
                   "n_snapshots", "duration_min_s", "duration_max_s", "left_censored",
                   "right_censored", "interrupted", "min_gap"]


def buy_discount_rate(events, r=R_BASE):
    """Discount rate for each row: r, less the holding reward for events that
    earn one (holding the basket until resolution earns the reward)."""
    reward = np.where(events.isin(HOLDING_REWARD_EVENTS), HOLDING_REWARD_RATE, 0.0)
    return r - pd.Series(reward, index=events.index)


def gap_values(df, side, q, r=R_BASE):
    """Gap for each row at size q; NaN where the basket isn't priceable."""
    price, fees = df[f"{side}_price_{q}"], df[f"{side}_fees_{q}"]
    if side == "buy":
        rate = buy_discount_rate(df["event"], r)
        gap = price + fees - (1.0 + rate) ** (-df["t_years"])
    else:
        gap = 1.0 - (price - fees)
    return gap.where(df[f"{side}_status_{q}"] == OK)


def classify(df, gap, staleness_cutoff=None):
    """State (N, V or U) of each row."""
    state = np.where(gap.isna(), U, np.where(gap < 0, V, N))
    unknown = (df["t_years"] <= 0).to_numpy()
    if staleness_cutoff is not None:
        unknown = unknown | (df["window_s"] > staleness_cutoff).to_numpy()
    return np.where(unknown, U, state)


def find_episodes(ticks, states, gaps, max_step=MAX_STEP_S):
    """Find episodes in one event's snapshots, given in time order."""
    ticks = np.asarray(ticks, dtype=float)
    states = np.asarray(states)
    gaps = np.asarray(gaps, dtype=float)
    if len(ticks) == 0:
        return []

    # Mark unknown snapshots, and missing time before any snapshot.
    time_gap = np.zeros(len(ticks), dtype=bool)
    time_gap[1:] = np.diff(ticks) > max_step
    marks = np.cumsum((states == U) | time_gap)

    known = np.flatnonzero(states != U)
    if len(known) == 0:
        return []
    k_ticks, k_gaps = ticks[known], gaps[known]
    k_viol = states[known] == V
    # unknown_before[k]: is there unknown data between known snapshot k-1 and k?
    unknown_before = np.empty(len(known), dtype=bool)
    unknown_before[0] = True
    unknown_before[1:] = np.diff(marks[known]) > 0

    edges = np.diff(np.concatenate([[0], k_viol.astype(int), [0]]))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1

    episodes = []
    for s, e in zip(starts, ends):
        left = bool(unknown_before[s])
        right = bool(e + 1 >= len(known) or unknown_before[e + 1])
        episodes.append({
            "start": k_ticks[s],
            "end": k_ticks[e],
            "prev_clean": np.nan if left else k_ticks[s - 1],
            "next_clean": np.nan if right else k_ticks[e + 1],
            "n_snapshots": int(e - s + 1),
            "duration_min_s": k_ticks[e] - k_ticks[s],
            "duration_max_s": (np.nan if left or right
                               else k_ticks[e + 1] - k_ticks[s - 1]),
            "left_censored": left,
            "right_censored": right,
            "interrupted": bool(unknown_before[s + 1:e + 1].any()),
            "min_gap": float(k_gaps[s:e + 1].min()),
        })
    return episodes


def episodes_for(df, side, q, r=R_BASE, staleness_cutoff=None):
    """All episodes for one side and size, across events."""
    gap = gap_values(df, side, q, r)
    work = pd.DataFrame({
        "tick": df["tick"].to_numpy(),
        "event": df["event"].to_numpy(),
        "state": classify(df, gap, staleness_cutoff),
        "gap": gap.to_numpy(),
    })
    rows = []
    for event, g in work.groupby("event", sort=True):
        g = g.sort_values("tick")
        for ep in find_episodes(g["tick"], g["state"], g["gap"]):
            rows.append({"event": event, "side": side, "size": q, **ep})
    return pd.DataFrame(rows, columns=EPISODE_COLUMNS)


def needed_columns():
    cols = ["tick", "event", "t_years", "window_s"]
    for side in ("buy", "sell"):
        for q in SIZES:
            cols += [f"{side}_status_{q}", f"{side}_price_{q}", f"{side}_fees_{q}"]
    return cols


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_processed(columns=needed_columns())
    parts = []
    for cutoff in (None, STALENESS_CUTOFF_S):
        for side in ("buy", "sell"):
            for q in SIZES:
                ep = episodes_for(df, side, q, staleness_cutoff=cutoff)
                ep["staleness_filter"] = cutoff is not None
                parts.append(ep)
    episodes = pd.concat(parts, ignore_index=True)
    for col in ("start", "end", "prev_clean", "next_clean"):
        episodes[col] = pd.to_datetime(episodes[col], unit="s", utc=True)
    episodes.to_csv(OUTPUT_DIR / "episodes.csv", index=False)

    closed = ~(episodes["left_censored"] | episodes["right_censored"])
    summary = episodes.assign(closed=closed).groupby(
        ["staleness_filter", "side", "size"]).agg(
        episodes=("event", "size"),
        closed=("closed", "sum"),
        median_min_s=("duration_min_s", "median"),
        median_max_s=("duration_max_s", "median"),
        longest_min_s=("duration_min_s", "max"),
        deepest_gap=("min_gap", "min"),
    )
    print(summary.round(4).to_string() if len(summary) else "No episodes found.")
    print(f"\n{len(episodes)} episode rows written to {OUTPUT_DIR / 'episodes.csv'}")


if __name__ == "__main__":
    main()
