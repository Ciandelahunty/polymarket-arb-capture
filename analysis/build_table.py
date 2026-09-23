"""Turn the raw collector files into one table per hour.

For every snapshot and event, records completeness, timing, and the cost of
buying and proceeds of selling the basket at each size. Output goes to
processed/books_YYYYMMDDHH.parquet. Only new or updated files are processed,
so this can be re-run as more data arrives.

Run from the repository folder:
    python analysis/build_table.py            # process new or updated files
    python analysis/build_table.py --force    # reprocess everything
"""
import argparse
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from costs import basket, years_between
from load import iter_snapshots, load_universe, server_seconds
from settings import DATA_DIR, PROCESSED_DIR, SIZES


def rows_for_snapshot(snap, events):
    tick = snap["tick"]
    by_token = {}
    for req in snap.get("requests", []):
        for b in req.get("books", []):
            by_token[b["token"]] = (b, req["sent"], req["received"])

    rows = []
    for ev in events:
        found = [by_token.get(t) for t in ev["tokens"]]
        books = [x[0] if x else None for x in found]
        present = [x for x in found if x]
        row = {
            "tick": tick,
            "event": ev["slug"],
            "n_legs": len(books),
            "n_present": len(present),
            "t_years": years_between(tick, ev["end_ts"]),
            "window_s": None, "age_min_s": None, "age_max_s": None,
        }
        if present:
            # Time within which every leg's book was read (conservative staleness).
            row["window_s"] = max(x[2] for x in present) - min(x[1] for x in present)
            ages = [x[2] - s for x in present
                    if (s := server_seconds(x[0].get("server_ts"))) is not None]
            if ages:
                row["age_min_s"], row["age_max_s"] = min(ages), max(ages)
        for q in SIZES:
            for side in ("buy", "sell"):
                status, price, fees = basket(books, ev["rates"], q, side)
                row[f"{side}_status_{q}"] = status
                row[f"{side}_price_{q}"] = price
                row[f"{side}_fees_{q}"] = fees
        rows.append(row)
    return rows


def process_file(path, out_path, events):
    stats = Counter()
    rows = []
    for snap in iter_snapshots(path, stats):
        stats["snapshots"] += 1
        rows.extend(rows_for_snapshot(snap, events))
    pd.DataFrame(rows).to_parquet(out_path, index=False)
    return path, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="reprocess every file")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    args = ap.parse_args()

    events = load_universe()
    PROCESSED_DIR.mkdir(exist_ok=True)
    todo = []
    for path in sorted(DATA_DIR.glob("books_*.jsonl.gz")):
        out = PROCESSED_DIR / path.name.replace(".jsonl.gz", ".parquet")
        if args.force or not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
            todo.append((path, out))
    if not todo:
        print("Nothing new to process.")
        return
    print(f"Processing {len(todo)} file(s) for {len(events)} events...")

    total = Counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process_file, p, o, events) for p, o in todo]
        for fut in futures:
            path, stats = fut.result()
            total.update(stats)
            note = (f", {stats['damaged_records']} damaged record(s) skipped"
                    if stats["damaged_records"] else "")
            print(f"  {path.name}: {stats['snapshots']} snapshots{note}")
    print(f"Done: {total['snapshots']} snapshots, "
          f"{total['damaged_records']} damaged record(s) skipped.")


if __name__ == "__main__":
    main()
