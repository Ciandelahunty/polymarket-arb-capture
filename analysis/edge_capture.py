"""Two checks for the CV figures: how complete the snapshot record is, and how
much of the apparent arbitrage edge a bot reacting 2 seconds late captures.

Run from the repository folder, after build_table.py:
    python analysis/edge_capture.py

1. Coverage. With one snapshot every 2 seconds, the number expected between the
   first and last snapshot, how many are missing, and the gaps they fall in.

2. Edge captured. The same sightings as the paper bot in results.py (the first
   snapshot of each violation at 1 basket). For each sighting and size:
   - apparent edge: the profit at the prices seen, as if trading instantly;
   - captured: the profit at the next snapshot's prices (about 2 seconds later),
     all or nothing, which is exactly what the paper bot earns;
   - capital: what the traded baskets cost (buy side) or raised (sell side);
   - fees: the taker fees paid on the traded baskets.
Gaps are after fees and discounting, so gross profit = captured + fees.
"""
import numpy as np
import pandas as pd

from episodes import V, classify, gap_values, needed_columns
from load import load_processed
from settings import MAX_STEP_S, SIZES

INTERVAL_S = 2.0
SIDES = ("buy", "sell")


def coverage(ticks):
    ticks = np.sort(np.unique(ticks))
    span = ticks[-1] - ticks[0]
    expected = int(round(span / INTERVAL_S)) + 1
    steps = np.diff(ticks)
    lost = np.maximum(np.round(steps / INTERVAL_S) - 1, 0)
    print("=== Coverage ===")
    print(f"Snapshots recorded: {len(ticks):,}")
    print(f"Expected at one every {INTERVAL_S:.0f} s over {span / 86400:.2f} days: {expected:,}")
    print(f"Missing: {expected - len(ticks):,} ({(expected - len(ticks)) / expected:.2%})")
    print(f"Median step {np.median(steps):.2f} s; steps over 3 s: {(steps > 3).sum():,}")
    gaps = pd.DataFrame({"start": pd.to_datetime(ticks[:-1], unit="s", utc=True),
                         "step_s": steps, "snapshots_lost": lost})
    gaps = gaps[gaps["snapshots_lost"] > 0]
    by_hour = gaps.groupby(gaps["start"].dt.floor("h"))["snapshots_lost"].sum()
    print("\nSnapshots lost by hour (hours losing 20 or more):")
    print(by_hour[by_hour >= 20].astype(int).to_string())
    print(f"Lost in other hours: {int(by_hour[by_hour < 20].sum()):,}")
    print("\nLongest single gaps:")
    print(gaps.nlargest(5, "step_s").to_string(index=False))


def sightings_for(df, side, q):
    rows = []
    for event, g in df.groupby("event", sort=True, observed=True):
        g = g.sort_values("tick").reset_index(drop=True)
        ticks = g["tick"].to_numpy(float)
        states = classify(g, g[f"{side}_gap_1"])
        close = np.zeros(len(g), dtype=bool)
        close[1:] = np.diff(ticks) <= MAX_STEP_S
        prev = np.zeros(len(g), dtype=bool)
        prev[1:] = (states[:-1] == V) & close[1:]
        gap_q = g[f"{side}_gap_{q}"].to_numpy(float)
        price = g[f"{side}_price_{q}"].to_numpy(float)
        fees = g[f"{side}_fees_{q}"].to_numpy(float)
        for i in np.flatnonzero((states == V) & ~prev):
            row = {"event": event, "apparent": max(-gap_q[i], 0) * q if not np.isnan(gap_q[i]) else 0.0,
                   "captured": 0.0, "traded": False, "capital": 0.0, "fees": 0.0, "undiscounted": 0.0}
            j = i + 1
            if j < len(g) and close[j] and not np.isnan(gap_q[j]) and gap_q[j] < 0:
                cost = price[j] + fees[j] if side == "buy" else price[j]
                # Undiscounted: $1 a basket at resolution minus what it cost, with no
                # allowance for the interest the money could have earned meanwhile.
                undiscounted = (1.0 - cost) * q if side == "buy" else -gap_q[j] * q
                row.update(captured=-gap_q[j] * q, traded=True, capital=cost * q, fees=fees[j] * q,
                           undiscounted=undiscounted)
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    df = load_processed(columns=needed_columns())
    coverage(df["tick"].to_numpy(float))
    df = df[df["t_years"] > 0].copy()
    for side in SIDES:
        for q in SIZES:
            df[f"{side}_gap_{q}"] = gap_values(df, side, q)

    print("\n=== Edge captured by a bot reacting one snapshot (about 2 s) late ===")
    out = []
    for side in SIDES:
        for q in SIZES:
            s = sightings_for(df, side, q)
            t = s[s["traded"]]
            out.append({
                "side": side, "size": q, "sightings": len(s),
                "apparent_edge_usd": s["apparent"].sum(),
                "trades": len(t),
                "captured_usd": s["captured"].sum(),
                "share_captured": s["captured"].sum() / s["apparent"].sum() if s["apparent"].sum() else np.nan,
                "capital_per_trade_usd": t["capital"].mean() if len(t) else np.nan,
                "profit_per_trade_usd": t["captured"].mean() if len(t) else np.nan,
                "return_per_trade": (t["captured"] / t["capital"]).mean() if len(t) else np.nan,
                "fees_usd": t["fees"].sum(),
                "undiscounted_usd": t["undiscounted"].sum(),
                "fee_share_of_gross": (t["fees"].sum() / (t["fees"].sum() + t["captured"].sum())
                                       if len(t) else np.nan),
            })
    table = pd.DataFrame(out).set_index(["side", "size"])
    pd.set_option("display.width", 200)
    print(table.round(4).to_string())
    t = table.fillna(0)
    capital = (t["capital_per_trade_usd"] * t["trades"]).sum()
    net, fees = t["captured_usd"].sum(), t["fees_usd"].sum()
    print(f"\nTrades taken: {int(t['trades'].sum()):,}, using ${capital:,.2f} of capital")
    print(f"Gross profit before fees ${net + fees:,.2f}; fees ${fees:,.2f} ({fees / (net + fees):.1%}); "
          f"net ${net:,.2f} ({net / capital:.2%} of capital, above the T-bill rate)")
    raw = t["undiscounted_usd"].sum()
    print(f"Undiscounted profit (\$1 at resolution minus cost, no interest deducted): ${raw:,.2f} "
          f"({raw / capital:.2%} of capital); the difference, ${raw - net:,.2f}, is what Treasury bills "
          "would have paid on the money until each event resolved")
    print("Note: share_captured compares the next snapshot with the sighting at the same size, so it can "
          "exceed 1 when the size-q violation appears or deepens a snapshot later.")

if __name__ == "__main__":
    main()
