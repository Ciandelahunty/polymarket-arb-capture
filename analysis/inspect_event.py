"""Look at one event's raw order books over a short period.

For each snapshot, prints the basket's buy-side gap at size 1 and each leg's
best ask (price x shares) with the age of its book. Polymarket's book timestamp
records when the book last changed, so it should never go backwards. A leg whose
timestamp is earlier than in the previous snapshot is marked "!": that response
was an older copy of the book than one already received.

Run from the repository folder, with times in UTC:
    python analysis/inspect_event.py maduro-prison-time-527 "2026-09-24 11:57:50" "2026-09-24 11:58:40"
"""
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from costs import OK, basket, discount_factor, years_between
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
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    slug, start, end = sys.argv[1], parse(sys.argv[2]), parse(sys.argv[3])
    event = next((e for e in load_universe() if e["slug"] == slug), None)
    if event is None:
        raise SystemExit(f"{slug} is not in universe.json")
    r = R_BASE - (HOLDING_REWARD_RATE if slug in HOLDING_REWARD_EVENTS else 0.0)

    print("Legs:", ", ".join(f"{i + 1}={label}" for i, label in enumerate(event["labels"])))
    print("Each leg: best ask x shares (seconds since its book last changed); ! = older than the previous snapshot\n")
    last_ts, went_back, count = {}, Counter(), 0
    for snap in sorted(snapshots_between(start, end), key=lambda s: s["tick"]):
        books = {}
        for req in snap.get("requests", []):
            for b in req.get("books", []):
                books[b["token"]] = (b, req["received"])
        legs = [books.get(t) for t in event["tokens"]]
        status, price, fees = basket([x[0] if x else None for x in legs], event["rates"], 1, "buy")
        par = discount_factor(r, years_between(snap["tick"], event["end_ts"]))
        gap = f"{(price + fees - par) * 100:+6.2f}c" if status == OK else f"{status:>7}"

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
            ask = book["asks"][0] if book["asks"] else None
            age = f"{received - ts:.0f}s" if ts is not None else "?"
            cells.append(f"{i + 1}: {ask[0]:.3f}x{ask[1]:.0f} ({age}){flag}" if ask else f"{i + 1}: no ask{flag}")
        count += 1
        when = datetime.fromtimestamp(snap["tick"], tz=timezone.utc)
        print(f"{when:%H:%M:%S}  gap {gap}  | " + " | ".join(cells))

    print(f"\n{count} snapshots. Book timestamps that went backwards, by leg: "
          + (", ".join(f"leg {k}: {v}" for k, v in sorted(went_back.items())) or "none"))


if __name__ == "__main__":
    main()
