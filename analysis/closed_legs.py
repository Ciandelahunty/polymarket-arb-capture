"""Record which markets in the sample have closed, when, and how they resolved.

Writes closed_legs.json in the repository folder, which build_table.py uses:
- a market that closed as No is left out of its event's basket from its
  closing time onwards (it is worth nothing with certainty, so the basket of
  the remaining outcomes still pays exactly $1);
- a market that closed as Yes means the event is decided, so the event's
  snapshots from that time onwards are treated as past its end date.

Run from the repository folder, at the end of collection (and again whenever
you want an up-to-date picture), then rebuild with --force:
    python analysis/closed_legs.py
    python analysis/build_table.py --force
"""
import json
import time

import pandas as pd
import requests

from settings import ROOT, UNIVERSE

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
OUT = ROOT / "closed_legs.json"
TIME_FIELDS = ("closedTime", "umaEndDate", "endDate")


def parse_list(value):
    return json.loads(value) if isinstance(value, str) else (value or [])


def yes_price(market):
    """Final YES price of a closed market: 1 = resolved Yes, 0 = resolved No,
    None if it can't be read."""
    outcomes = parse_list(market.get("outcomes"))
    prices = parse_list(market.get("outcomePrices"))
    if "Yes" not in outcomes or len(prices) != len(outcomes):
        return None
    try:
        return float(prices[outcomes.index("Yes")])
    except (TypeError, ValueError):
        return None


def main():
    with open(UNIVERSE) as f:
        events = json.load(f)["events"]
    closed, problems = {}, []
    for ev in events:
        tokens = {m["yes_token"]: m.get("label") for m in ev["markets"]}
        found = requests.get(GAMMA_EVENTS, params={"slug": ev["slug"]}, timeout=20).json()
        if not found:
            problems.append(f"{ev['slug']}: not found on Gamma")
            continue
        for m in found[0].get("markets", []):
            if not m.get("closed"):
                continue
            outcomes = parse_list(m.get("outcomes"))
            ids = parse_list(m.get("clobTokenIds"))
            if "Yes" not in outcomes or len(ids) != len(outcomes):
                continue
            token = ids[outcomes.index("Yes")]
            if token not in tokens:
                continue
            ts = None
            for field in TIME_FIELDS:
                if m.get(field):
                    try:
                        t = pd.Timestamp(m[field])
                        t = t.tz_localize("UTC") if t.tzinfo is None else t
                        ts, source = t.timestamp(), field
                        break
                    except (ValueError, TypeError):
                        pass
            price = yes_price(m)
            if ts is None or price is None or price not in (0.0, 1.0):
                problems.append(f"{ev['slug']} / {tokens[token]}: closed, but closing time "
                                f"or result unclear (time={ts}, yes price={price}); left in")
                continue
            closed[token] = {"event": ev["slug"], "label": tokens[token],
                             "closed_ts": ts, "time_field": source,
                             "resolved": "Yes" if price == 1.0 else "No"}
        time.sleep(0.1)

    with open(OUT, "w") as f:
        json.dump(closed, f, indent=2)
    print(f"{len(closed)} closed market(s) written to {OUT.name}:")
    for c in sorted(closed.values(), key=lambda c: (c["event"], c["closed_ts"])):
        when = pd.to_datetime(c["closed_ts"], unit="s", utc=True)
        print(f"  {c['event'][:45]:45s} {str(c['label'])[:12]:12s} resolved {c['resolved']:3s} "
              f"at {when:%d %b %H:%M} UTC (from {c['time_field']})")
    for p in problems:
        print("CHECK:", p)


if __name__ == "__main__":
    main()
