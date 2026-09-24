"""Results: the five results in ANALYSIS_PLAN.md, the robustness checks, and a
paper-trading bot.

Run from the repository folder, after build_table.py:
    python analysis/results.py

Prints a report, and saves it with its tables and charts to
analysis/output/results/. Gaps are reported in cents per basket.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from costs import OK
from episodes import N, U, V, classify, episodes_for, gap_values, needed_columns
from load import load_processed
from settings import (MAX_STEP_S, OUTPUT_DIR, R_BASE, R_SENSITIVITY, SIZES,
                      STALENESS_CUTOFF_S, UNIVERSE)

RESULTS_DIR = OUTPUT_DIR / "results"
SIDES = ("buy", "sell")
LARGE = SIZES[-1]


class Report:
    """Prints each part of the report and keeps it for saving as Markdown."""

    def __init__(self):
        self.parts = []

    def heading(self, title):
        self._add(f"\n## {title}\n")

    def text(self, s):
        self._add(s)

    def table(self, df, name=None):
        self._add("```\n" + df.to_string() + "\n```")
        if name:
            df.to_csv(RESULTS_DIR / f"{name}.csv")

    def _add(self, s):
        print(s)
        self.parts.append(s)

    def save(self):
        (RESULTS_DIR / "results.md").write_text("\n".join(self.parts) + "\n")


def add_gaps(df, r=R_BASE):
    """Gap columns for every side and size; NaN where not usable."""
    usable = df["t_years"] > 0
    for side in SIDES:
        for q in SIZES:
            df[f"{side}_gap_{q}"] = gap_values(df, side, q, r).where(usable)


# --- Paper-trading bot -----------------------------------------------------

def paper_trades(ticks, states_1, gaps_q, q, max_step=MAX_STEP_S):
    """A bot that watches prices for one basket and, on first seeing a
    violation, tries to trade q baskets at the next snapshot at that snapshot's
    prices. The order is all-or-nothing: if the basket is no longer in
    violation at size q, nothing trades.

    Returns one dict per sighting, with outcome "traded", "gone" (no longer
    profitable at size q) or "unknown" (next snapshot missing or unpriceable),
    and the profit in dollars.
    """
    ticks = np.asarray(ticks, dtype=float)
    states_1 = np.asarray(states_1)
    gaps_q = np.asarray(gaps_q, dtype=float)
    n = len(ticks)
    close = np.zeros(n, dtype=bool)
    close[1:] = np.diff(ticks) <= max_step
    prev_violation = np.zeros(n, dtype=bool)
    prev_violation[1:] = (states_1[:-1] == V) & close[1:]
    sightings = np.flatnonzero((states_1 == V) & ~prev_violation)

    out = []
    for i in sightings:
        j = i + 1
        if j >= n or not close[j] or np.isnan(gaps_q[j]):
            out.append({"seen": ticks[i], "outcome": "unknown", "pnl": 0.0})
        elif gaps_q[j] < 0:
            out.append({"seen": ticks[i], "outcome": "traded", "pnl": -gaps_q[j] * q})
        else:
            out.append({"seen": ticks[i], "outcome": "gone", "pnl": 0.0})
    return out


def run_bot(df, side, q):
    rows = []
    for event, g in df.groupby("event", sort=True, observed=True):
        g = g.sort_values("tick")
        states = classify(g, g[f"{side}_gap_1"])
        for t in paper_trades(g["tick"], states, g[f"{side}_gap_{q}"], q):
            rows.append({"event": event, "side": side, "size": q, **t})
    return pd.DataFrame(rows, columns=["event", "side", "size", "seen", "outcome", "pnl"])


# --- Capture rate ------------------------------------------------------------

def capture_at_snapshots(gap_1, gap_q):
    """Of snapshots in violation at size 1, how many are also in violation at
    size q, no longer in violation, or unpriceable at size q."""
    visible = gap_1 < 0
    g = gap_q[visible]
    remain, gone = int((g < 0).sum()), int((g >= 0).sum())
    return {
        "visible_at_1": int(visible.sum()),
        "remain": remain,
        "gone": gone,
        "unknown": int(g.isna().sum()),
        "capture_rate": remain / (remain + gone) if remain + gone else np.nan,
    }


def capture_in_episodes(episodes, df, side, q):
    """Share of size-1 episodes during which the basket was also in violation
    at size q at some snapshot."""
    ep = episodes[(episodes["side"] == side) & (episodes["size"] == 1)]
    hits = 0
    for e in ep.itertuples():
        g = df[(df["event"] == e.event) & (df["tick"] >= e.start) & (df["tick"] <= e.end)]
        hits += bool((g[f"{side}_gap_{q}"] < 0).any())
    return {"episodes_at_1": len(ep), "with_violation_at_q": hits,
            "share": hits / len(ep) if len(ep) else np.nan}


# --- Main ---------------------------------------------------------------------

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rep = Report()
    df = load_processed(columns=needed_columns() + ["age_max_s"])
    with open(UNIVERSE) as f:
        universe = {e["slug"]: e for e in json.load(f)["events"]}

    start = pd.to_datetime(df["tick"].min(), unit="s", utc=True)
    end = pd.to_datetime(df["tick"].max(), unit="s", utc=True)
    rep.text(f"# Results\n\nData: {df['tick'].nunique():,} snapshots of {df['event'].nunique()} "
             f"events, {start:%d %b %H:%M} to {end:%d %b %H:%M} UTC. "
             f"Gaps in cents per basket; negative = violation. r = {R_BASE:.2%}.")

    # Discount rate sensitivity needs the raw prices, so do it first.
    sens = []
    for r in sorted(set(R_SENSITIVITY) | {R_BASE}):
        row = {"r": r}
        for q in SIZES:
            g = gap_values(df, "buy", q, r).where(df["t_years"] > 0)
            row[f"median_gap_{q}"] = g.median() * 100
            row[f"violations_{q}"] = int((g < 0).sum())
        row["episodes_1"] = len(episodes_for(df, "buy", 1, r=r))
        sens.append(row)

    # Episodes at the baseline rate, with and without the staleness filter.
    episodes = pd.concat(
        [episodes_for(df, side, q, staleness_cutoff=cut).assign(staleness_filter=cut is not None)
         for cut in (None, STALENESS_CUTOFF_S) for side in SIDES for q in SIZES],
        ignore_index=True)

    add_gaps(df)
    df.drop(columns=[c for c in df.columns if "_price_" in c or "_fees_" in c], inplace=True)
    base_eps = episodes[~episodes["staleness_filter"]]

    # 1. The gap.
    rep.heading("1. The gap")
    rows = []
    for side in SIDES:
        for q in SIZES:
            g = df[f"{side}_gap_{q}"].dropna() * 100
            rows.append({"side": side, "size": q, "snapshots": len(g),
                         "p5": g.quantile(.05), "p25": g.quantile(.25), "median": g.median(),
                         "p75": g.quantile(.75), "p95": g.quantile(.95), "min": g.min()})
    rep.table(pd.DataFrame(rows).set_index(["side", "size"]).round(2), "gap_distribution")

    fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    for ax, side in zip(axes, SIDES):
        for q in (1, LARGE):
            g = (df[f"{side}_gap_{q}"].dropna() * 100).clip(-5, 60)
            ax.hist(g, bins=260, range=(-5, 60), histtype="step", density=True, label=f"size {q}")
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(f"{side.capitalize()} side")
        ax.set_xlabel("gap (cents per basket); left of 0 = violation")
        ax.legend()
    axes[0].set_ylabel("share of snapshots (density)")
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "gap_distribution.png", dpi=120)
    plt.close()

    # 2. Frequency.
    rep.heading("2. Frequency")
    rows = []
    for cut in (None, STALENESS_CUTOFF_S):
        sub = df if cut is None else df[df["window_s"] <= cut]
        for side in SIDES:
            for q in SIZES:
                g = sub[f"{side}_gap_{q}"]
                priced = int(g.notna().sum())
                below = int((g < 0).sum())
                rows.append({"staleness_filter": cut is not None, "side": side, "size": q,
                             "snapshots": len(sub), "priceable": priced,
                             "share_priceable": priced / len(sub) if len(sub) else np.nan,
                             "in_violation": below,
                             "share_in_violation": below / priced if priced else np.nan})
    rep.table(pd.DataFrame(rows).set_index(["staleness_filter", "side", "size"]).round(6),
              "frequency")

    # 3. Survival.
    rep.heading("3. Survival: violation episodes")
    if len(episodes):
        closed = ~(episodes["left_censored"] | episodes["right_censored"])
        summary = episodes.assign(closed=closed).groupby(["staleness_filter", "side", "size"]).agg(
            episodes=("event", "size"), closed=("closed", "sum"),
            median_lower_s=("duration_min_s", "median"),
            median_upper_s=("duration_max_s", "median"),
            longest_lower_s=("duration_min_s", "max"),
            deepest_gap_c=("min_gap", lambda s: s.min() * 100))
        rep.table(summary.round(2), "survival")
        listing = base_eps.copy()
        for col in ("start", "end"):
            listing[col] = pd.to_datetime(listing[col], unit="s", utc=True)
        listing["min_gap"] = listing["min_gap"] * 100
        listing.to_csv(RESULTS_DIR / "episodes.csv", index=False)

        size1 = base_eps[(base_eps["size"] == 1)
                         & ~(base_eps["left_censored"] | base_eps["right_censored"])]
        if len(size1):
            fig, ax = plt.subplots(figsize=(9, 0.35 * len(size1) + 1.5))
            size1 = size1.sort_values("duration_min_s").reset_index(drop=True)
            for i, e in size1.iterrows():
                colour = "tab:blue" if e["side"] == "buy" else "tab:orange"
                ax.plot([e["duration_min_s"], e["duration_max_s"]], [i, i], color=colour, lw=3)
            ax.set_yticks(range(len(size1)))
            ax.set_yticklabels([f"{e.side} · {e.event[:30]}" for e in size1.itertuples()], fontsize=7)
            ax.set_xlabel("duration (seconds): each bar spans the lower to upper bound")
            ax.set_title("Violation episodes at size 1 (fully observed only)")
            plt.tight_layout()
            plt.savefig(RESULTS_DIR / "episodes.png", dpi=120)
            plt.close()
    else:
        rep.text("No episodes.")

    # 4. Capture rate.
    rep.heading("4. Capture rate")
    rep.text("At the same snapshot: of snapshots in violation at size 1, how many are "
             "still in violation at the larger size.")
    rows = []
    for cut in (None, STALENESS_CUTOFF_S):
        sub = df if cut is None else df[df["window_s"] <= cut]
        for side in SIDES:
            for q in SIZES[1:]:
                rows.append({"staleness_filter": cut is not None, "side": side, "size": q,
                             **capture_at_snapshots(sub[f"{side}_gap_1"], sub[f"{side}_gap_{q}"])})
    rep.table(pd.DataFrame(rows).set_index(["staleness_filter", "side", "size"]).round(4),
              "capture_snapshots")
    rep.text("\nWithin episodes: of episodes at size 1, how many reach a violation at the "
             "larger size at any point.")
    rows = [{"side": side, "size": q, **capture_in_episodes(base_eps, df, side, q)}
            for side in SIDES for q in SIZES[1:]]
    rep.table(pd.DataFrame(rows).set_index(["side", "size"]).round(4), "capture_episodes")

    # Paper-trading bot.
    rep.heading("Paper-trading bot")
    rep.text("On first seeing a violation at size 1, the bot tries to trade at the next snapshot "
             "(about 2 seconds later) at that snapshot's prices, all or nothing. Buy-side profit "
             "is in today's money and is realised at resolution; sell-side profit is immediate.")
    trades = pd.concat([run_bot(df, side, q) for side in SIDES for q in SIZES], ignore_index=True)
    if len(trades):
        trades["seen"] = pd.to_datetime(trades["seen"], unit="s", utc=True)
        trades.to_csv(RESULTS_DIR / "paper_trades.csv", index=False)
    summary = (trades.groupby(["side", "size"])
               .agg(sightings=("outcome", "size"),
                    traded=("outcome", lambda s: (s == "traded").sum()),
                    gone=("outcome", lambda s: (s == "gone").sum()),
                    unknown=("outcome", lambda s: (s == "unknown").sum()),
                    total_profit_usd=("pnl", "sum"))
               if len(trades) else pd.DataFrame())
    rep.table(summary.round(4) if len(summary) else pd.DataFrame({"sightings": [0]}), "paper_bot")

    # 5. Attention.
    rep.heading("5. Attention: events ranked by 24-hour volume at the start of collection")
    g = df.groupby("event", observed=True)
    ep1 = base_eps[base_eps["size"] == 1].groupby(["event", "side"]).size().unstack(fill_value=0)
    events = pd.DataFrame({
        "volume_24h_usd": pd.Series({s: float(e.get("volume24hr") or 0) for s, e in universe.items()}),
        "outcomes": pd.Series({s: sum(not m.get("closed") for m in e["markets"])
                               for s, e in universe.items()}),
        "buy_median_gap_c": g["buy_gap_1"].median() * 100,
        "sell_median_gap_c": g["sell_gap_1"].median() * 100,
        "buy_violation_share": g["buy_gap_1"].apply(lambda s: (s < 0).sum() / max(s.notna().sum(), 1)),
        "sell_violation_share": g["sell_gap_1"].apply(lambda s: (s < 0).sum() / max(s.notna().sum(), 1)),
        "buy_episodes": ep1["buy"] if "buy" in ep1 else 0,
        "sell_episodes": ep1["sell"] if "sell" in ep1 else 0,
        "median_quote_age_s": g["age_max_s"].median(),
    })
    events[["buy_episodes", "sell_episodes"]] = events[["buy_episodes", "sell_episodes"]].fillna(0).astype(int)
    events = events.sort_values("volume_24h_usd", ascending=False)
    events.insert(0, "volume_rank", range(1, len(events) + 1))
    events.index.name = "event"
    shown = events.copy()
    shown.index = [s[:55] for s in shown.index]
    rep.table(shown.round(3), "attention_events")

    rep.text("\nRank correlation (Spearman) of each measure with 24-hour volume and with the "
             "number of outcomes. With 20 correlated events, treat these as descriptive.")
    cols = ["buy_median_gap_c", "sell_median_gap_c", "buy_violation_share",
            "sell_violation_share", "median_quote_age_s"]
    corr = events[["volume_24h_usd", "outcomes"] + cols].corr(method="spearman")
    rep.table(corr.loc[cols, ["volume_24h_usd", "outcomes"]].round(2), "attention_correlations")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for side, colour in (("buy", "tab:blue"), ("sell", "tab:orange")):
        axes[0].scatter(events["volume_24h_usd"].clip(lower=1), events[f"{side}_median_gap_c"],
                        color=colour, label=f"{side} side")
    axes[0].set_xscale("log")
    axes[0].set_xlabel("24-hour volume at start (USD, log scale)")
    axes[0].set_ylabel("median gap at size 1 (cents)")
    axes[0].legend()
    axes[1].scatter(events["median_quote_age_s"], events["buy_median_gap_c"], color="tab:blue", label="buy side")
    axes[1].scatter(events["median_quote_age_s"], events["sell_median_gap_c"], color="tab:orange", label="sell side")
    axes[1].set_xlabel("median age of the stalest leg's quote (seconds)")
    axes[1].legend()
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "attention.png", dpi=120)
    plt.close()

    # Robustness.
    rep.heading("Robustness: discount rate (buy side)")
    rep.table(pd.DataFrame(sens).set_index("r").round(3), "rate_sensitivity")
    rep.text("\nThe staleness filter appears in the frequency, survival and capture tables above.")

    rep.save()
    print(f"\nReport, tables and charts saved to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
