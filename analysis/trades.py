"""Download Polymarket trades for every market in the sample over the collection
period, so each violation episode can be matched with the trades around it.

Saves data/trades.parquet (one row per trade, from the side of the trader who
took the order) and data/trade_markets.json (each market's event and tokens).
Re-running downloads the whole period again, which is quick.

Run from the repository folder:
    python analysis/trades.py
"""
import argparse
import json
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from settings import DATA_DIR, UNIVERSE

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
TRADES = "https://data-api.polymarket.com/trades"
PAGE = 500            # trades per request (the API's maximum)
OFFSET_CAP = 10_000   # the API rejects offsets beyond this; narrower windows get round it
WINDOW_S = 6 * 3600   # fetch each market in 6-hour windows
KEEP = ["timestamp", "conditionId", "asset", "side", "size", "price",
        "transactionHash", "proxyWallet"]

session = requests.Session()


def get(url, params, retries=5):
    """GET with retries, backing off if the API asks us to slow down."""
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gave up on {url} after {retries} attempts")


def parse_list(value):
    return json.loads(value) if isinstance(value, str) else (value or [])


def market_map(slugs):
    """Each market's event, label, condition ID and YES and NO tokens."""
    rows = []
    for slug in slugs:
        found = get(GAMMA_EVENTS, {"slug": slug})
        if not found:
            print(f"  Not found on Gamma: {slug}")
            continue
        for m in found[0].get("markets", []):
            outcomes, tokens = parse_list(m.get("outcomes")), parse_list(m.get("clobTokenIds"))
            if sorted(outcomes) != ["No", "Yes"] or len(tokens) != 2:
                continue
            rows.append({"event": slug,
                         "label": m.get("groupItemTitle") or m.get("question"),
                         "condition_id": m["conditionId"],
                         "yes_token": tokens[outcomes.index("Yes")],
                         "no_token": tokens[outcomes.index("No")]})
        time.sleep(0.1)
    return rows


def fetch_window(fetch, start, end, page=PAGE, cap=OFFSET_CAP):
    """Every trade with start <= timestamp <= end. `fetch(start, end, offset)`
    returns one page. If the window holds more trades than the offset cap
    allows, it's split in two and each half fetched separately."""
    out, offset = [], 0
    while True:
        if offset + page > cap:
            mid = (start + end) // 2
            if mid <= start:
                raise RuntimeError(f"More than {cap} trades within one second at {start}")
            return (fetch_window(fetch, start, mid, page, cap)
                    + fetch_window(fetch, mid + 1, end, page, cap))
        batch = fetch(start, end, offset)
        out.extend(batch)
        if len(batch) < page:
            return out
        offset += page


def fetch_market(condition_id, start, end):
    def page(s, e, offset):
        return get(TRADES, {"market": condition_id, "start": s, "end": e,
                            "limit": PAGE, "offset": offset})
    trades = []
    for s in range(start, end + 1, WINDOW_S):
        trades += fetch_window(page, s, min(s + WINDOW_S - 1, end))
        time.sleep(0.05)
    return trades


def to_epoch(text):
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-22T17:00:00Z", help="UTC, e.g. 2026-09-22T17:00:00Z")
    ap.add_argument("--end", default=None, help="UTC; default now")
    args = ap.parse_args()
    start = to_epoch(args.start)
    end = to_epoch(args.end) if args.end else int(time.time())

    with open(UNIVERSE) as f:
        slugs = [e["slug"] for e in json.load(f)["events"]]
    print(f"Looking up markets for {len(slugs)} events...")
    markets = market_map(slugs)
    with open(DATA_DIR / "trade_markets.json", "w") as f:
        json.dump(markets, f, indent=2)

    print(f"Downloading trades for {len(markets)} markets...")
    frames = []
    for i, m in enumerate(markets, 1):
        t = fetch_market(m["condition_id"], start, end)
        print(f"  [{i}/{len(markets)}] {m['event'][:40]} · {str(m['label'])[:30]}: {len(t)} trades")
        if t:
            df = pd.DataFrame(t)
            missing = [c for c in KEEP if c not in df.columns]
            if missing:
                print(f"    Fields missing from the API response: {missing}")
            df = df[[c for c in KEEP if c in df.columns]]
            df["event"] = m["event"]
            df["is_yes"] = df["asset"] == m["yes_token"]
            frames.append(df)

    if not frames:
        raise SystemExit("No trades found.")
    trades = pd.concat(frames, ignore_index=True).drop_duplicates()
    trades = trades.sort_values("timestamp").reset_index(drop=True)
    trades.to_parquet(DATA_DIR / "trades.parquet", index=False)
    print(f"Saved {len(trades):,} trades to {DATA_DIR / 'trades.parquet'}")


if __name__ == "__main__":
    main()
