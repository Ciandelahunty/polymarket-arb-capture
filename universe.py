"""Build universe.json from the event slugs in slugs.txt using the Gamma API.

Run this once before starting the collector, and again whenever you change
slugs.txt. Commit the resulting universe.json to git: it is the record of
which events were sampled and what their properties were at the start.
"""
import json
import time

import requests

GAMMA_EVENTS = "https://gamma-api.polymarket.com/events"
SLUGS_FILE = "slugs.txt"
OUT_FILE = "universe.json"


def parse_list(value):
    """Gamma returns some list fields as JSON-encoded strings."""
    if isinstance(value, str):
        return json.loads(value)
    return value or []


def fee_fields(d):
    """Keep every field whose name mentions 'fee', so the rate is captured
    whatever Gamma calls it."""
    return {k: v for k, v in d.items() if "fee" in k.lower()}


def main():
    with open(SLUGS_FILE) as f:
        slugs = [s.strip() for s in f if s.strip() and not s.startswith("#")]

    events, problems = [], []
    for slug in slugs:
        r = requests.get(GAMMA_EVENTS, params={"slug": slug}, timeout=20)
        r.raise_for_status()
        found = r.json()
        if not found:
            problems.append(f"{slug}: not found (check it is the event slug)")
            continue
        ev = found[0]
        if not ev.get("negRisk"):
            problems.append(f"{slug}: negRisk is not true")
        if ev.get("negRiskAugmented"):
            problems.append(f"{slug}: negRiskAugmented is true")

        markets = []
        for m in ev.get("markets", []):
            outcomes = parse_list(m.get("outcomes"))
            tokens = parse_list(m.get("clobTokenIds"))
            if "Yes" not in outcomes or len(tokens) != len(outcomes):
                problems.append(f"{slug}: unexpected format in '{m.get('question')}'")
                continue
            markets.append({
                "market_id": m.get("id"),
                "label": m.get("groupItemTitle") or m.get("question"),
                "yes_token": tokens[outcomes.index("Yes")],
                "active": m.get("active"),
                "closed": m.get("closed"),
                "fees": fee_fields(m),
            })

        if len(markets) < 3:
            problems.append(f"{slug}: only {len(markets)} usable outcomes")

        events.append({
            "slug": slug,
            "title": ev.get("title"),
            "end_date": ev.get("endDate"),
            "volume24hr": ev.get("volume24hr"),
            "liquidity": ev.get("liquidity"),
            "fees": fee_fields(ev),
            "markets": markets,
        })
        time.sleep(0.2)

    with open(OUT_FILE, "w") as f:
        json.dump({"built_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "events": events}, f, indent=2)

    n_open = sum(1 for e in events for m in e["markets"] if not m["closed"])
    print(f"{len(events)} events, {n_open} open markets written to {OUT_FILE}")
    for p in problems:
        print("CHECK:", p)


if __name__ == "__main__":
    main()
