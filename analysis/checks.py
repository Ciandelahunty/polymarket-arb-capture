"""Sanity checks and a first look at the processed table.

Prints a report and saves figures to analysis/output/. Run from the
repository folder after build_table.py:
    python analysis/checks.py
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from costs import OK
from load import load_universe
from settings import OUTPUT_DIR, POLL_INTERVAL_S, PROCESSED_DIR, R_BASE, SIZES, STALENESS_CUTOFF_S


def load_processed():
    files = sorted(PROCESSED_DIR.glob("*.parquet"))
    if not files:
        raise SystemExit("No processed files found. Run analysis/build_table.py first.")
    return pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)


def add_gaps(df, r):
    discount = (1.0 + r) ** (-df["t_years"])
    for q in SIZES:
        df[f"buy_gap_{q}"] = df[f"buy_price_{q}"] + df[f"buy_fees_{q}"] - discount
        df[f"sell_gap_{q}"] = 1.0 - (df[f"sell_price_{q}"] - df[f"sell_fees_{q}"])
    return df


def section(title):
    print(f"\n=== {title} ===")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    events = load_universe()
    df = load_processed()
    df["time"] = pd.to_datetime(df["tick"], unit="s", utc=True)
    df = add_gaps(df, R_BASE)

    # 1. Coverage: snapshots per hour.
    section("Coverage")
    ticks = df.drop_duplicates("tick")
    per_hour = ticks.groupby(ticks["time"].dt.floor("h")).size()
    expected = 3600 / POLL_INTERVAL_S
    print(f"{len(ticks)} snapshots from {ticks['time'].min()} to {ticks['time'].max()}")
    short = per_hour[per_hour < 0.95 * expected]
    print(f"Hours below 95% of the expected {expected:.0f} snapshots "
          "(first and last hours are usually partial):")
    print(short.to_string() if len(short) else "  none")
    ax = per_hour.plot(kind="bar", figsize=(14, 4), title="Snapshots per hour (UTC)")
    ax.set_xticklabels([t.strftime("%d %H:00") for t in per_hour.index], fontsize=7)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "coverage.png", dpi=120)
    plt.close()

    # 2. Fee rates used, so they can be checked against what Polymarket shows.
    section("Fee rates by event")
    for ev in events:
        rates = sorted(set(ev["rates"]))
        print(f"  {ev['slug'][:60]:60s} rate {rates}  (from {ev['rate_sources'][0]})")

    # 3. Completeness and fill status.
    section("Completeness: share of snapshots with every leg present")
    comp = (df["n_present"] == df["n_legs"]).groupby(df["event"]).mean()
    print(comp.sort_values().round(4).to_string())
    for side in ("buy", "sell"):
        section(f"{side.capitalize()} basket status by size (share of rows)")
        table = pd.DataFrame({q: df[f"{side}_status_{q}"].value_counts(normalize=True)
                              for q in SIZES}).fillna(0).round(4)
        print(table.to_string())

    # 4. Timing.
    section("Timing (seconds)")
    print("Read window across each event's legs (staleness):")
    print(df["window_s"].describe(percentiles=[.5, .9, .99]).round(3).to_string())
    print(f"Share of rows above the {STALENESS_CUTOFF_S}s cutoff: "
          f"{(df['window_s'] > STALENESS_CUTOFF_S).mean():.4f}")
    print("\nResponse time minus Polymarket's book timestamp, min and max across legs:")
    print(df[["age_min_s", "age_max_s"]].describe(percentiles=[.5, .9]).round(2).to_string())
    print("If both are near zero, the timestamp is when the book was sent. If the max is\n"
          "often minutes or more, it is when each book last changed.")

    # 5. Gaps at the baseline rate.
    for side in ("buy", "sell"):
        section(f"{side.capitalize()}-side gap at r = {R_BASE:.3f} (negative = violation)")
        summary = []
        for q in SIZES:
            g = df.loc[df[f"{side}_status_{q}"] == OK, f"{side}_gap_{q}"]
            summary.append({"size": q, "rows_ok": len(g), "median": g.median(),
                            "min": g.min(), "n_below_zero": int((g < 0).sum()),
                            "share_below_zero": (g < 0).mean() if len(g) else float("nan")})
        print(pd.DataFrame(summary).set_index("size").round(5).to_string())
        by_event = df.groupby("event")[f"{side}_gap_1"].agg(["median", "min"])
        by_event["n_below_zero"] = (df[f"{side}_gap_1"] < 0).groupby(df["event"]).sum()
        print(f"\nBy event, size 1:")
        print(by_event.sort_values("min").round(5).to_string())

    # 6. Gap over time per event: per-minute minimum, sizes 1 and 500.
    for side in ("buy", "sell"):
        n = len(events)
        cols = 4
        rows = -(-n // cols)
        fig, axes = plt.subplots(rows, cols, figsize=(18, 3 * rows), sharex=True)
        for ax, ev in zip(axes.flat, events):
            sub = df[df["event"] == ev["slug"]].set_index("time")
            for q in (SIZES[0], SIZES[-1]):
                s = sub[f"{side}_gap_{q}"].resample("1min").min()
                ax.plot(s.index, s.values, lw=0.7, label=f"size {q}")
            ax.axhline(0, color="black", lw=0.6)
            ax.set_title(ev["slug"][:45], fontsize=8)
            ax.tick_params(labelsize=7)
            locator = mdates.AutoDateLocator()
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        for ax in list(axes.flat)[n:]:
            ax.axis("off")
        axes.flat[0].legend(fontsize=7)
        fig.suptitle(f"{side.capitalize()}-side gap, per-minute minimum (below zero = violation)")
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / f"gaps_{side}.png", dpi=110)
        plt.close()

    print(f"\nFigures saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
