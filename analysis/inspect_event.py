"""Look at one event's raw order books over a short period.

For each snapshot, prints the basket's gap at size 1 and, for each leg, the
best price on that side (price x shares) with the age of its book. Buy side
(default) shows asks; --side sell shows bids. Polymarket's book timestamp
records when the book last changed, so it should never go backwards. A leg whose
timestamp is earlier than in the previous snapshot is marked "!": that response
was an older copy of the book than one already received.

Run from the repository folder, with times in UTC:
    python analysis/inspect_event.py maduro-prison-time-527 "2026-09-24 11:57:50" "2026-09-24 11:58:40"
    python analysis/inspect_event.py <slug> "<start>" "<end>" --side sell
"""
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from costs import OK, basket, discount_factor, sell_gap, years_between
from load import iter_snapshots, load_universe, server_seconds
from settings import DATA_DIR, HOLDING_REWARD_EVENTS, HOLDING_REWARD_RATE, R_BASE


def parse(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def snapshots_between(start, end):
    hour = start.replace(minute=0, second=0)
    stats = Counter()
    while hour <= end:
        path = DATA_DIR / f"books_{hour:%Y%m%d%H}.jsonl.gz"
        if path.exists():
            for snap in iter_snapshots(path, stats):
                if start.timestamp() <= snap["tick"] <= end.timestamp():
                    yield snap
        hour += timedelta(hours=1)


def main():
    args = sys.argv[1:]
    side = "buy"
    if "--side" in args:
        i = args.index("--side")
        side = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3 or side not in ("buy", "sell"):
        raise SystemExit(__doc__)
    slug, start, end = args[0], parse(args[1]), parse(args[2])
    key = "asks" if side == "buy" else "bids"
    event = next((e for e in load_universe() if e["slug"] == slug), None)
    if event is None:
        raise SystemExit(f"{slug} is not in universe.json")
    r = R_BASE - (HOLDING_REWARD_RATE if slug in HOLDING_REWARD_EVENTS else 0.0)

    print("Legs:", ", ".join(f"{i + 1}={label}" for i, label in enumerate(event["labels"])))
    label = "best ask" if side == "buy" else "best bid"
    print(f"{side.capitalize()} side. Each leg: {label} x shares (seconds since its book last changed); "
          "! = older than the previous snapshot\n")
    last_ts, went_back, count = {}, Counter(), 0
    for snap in sorted(snapshots_between(start, end), key=lambda s: s["tick"]):
        books = {}
        for req in snap.get("requests", []):
            for b in req.get("books", []):
                books[b["token"]] = (b, req["received"])
        legs = [books.get(t) for t in event["tokens"]]
        status, price, fees = basket([x[0] if x else None for x in legs], event["rates"], 1, side)
        if status != OK:
            gap = f"{status:>7}"
        elif side == "buy":
            par = discount_factor(r, years_between(snap["tick"], event["end_ts"]))
            gap = f"{(price + fees - par) * 100:+6.2f}c"
        else:
            gap = f"{sell_gap(price, fees) * 100:+6.2f}c"

        cells = []
        for i, (token, leg) in enumerate(zip(event["tokens"], legs)):
            if leg is None:
                cells.append(f"{i + 1}: missing")
                continue
            book, received = leg
            ts = server_seconds(book.get("server_ts"))
            flag = ""
            if ts is not None and token in last_ts and ts < last_ts[token]:
                flag = "!"
                went_back[i + 1] += 1
            if ts is not None:
                last_ts[token] = ts
            best = book[key][0] if book[key] else None
            age = f"{received - ts:.0f}s" if ts is not None else "?"
            cells.append(f"{i + 1}: {best[0]:.3f}x{best[1]:.0f} ({age}){flag}" if best
                         else f"{i + 1}: no {key[:-1]}{flag}")
        count += 1
        when = datetime.fromtimestamp(snap["tick"], tz=timezone.utc)
        print(f"{when:%H:%M:%S}  gap {gap}  | " + " | ".join(cells))

    print(f"\n{count} snapshots. Book timestamps that went backwards, by leg: "
          + (", ".join(f"leg {k}: {v}" for k, v in sorted(went_back.items())) or "none"))


if __name__ == "__main__":
    main()
