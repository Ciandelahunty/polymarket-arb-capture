"""Poll the order book of every open YES token in universe.json.

Writes one line per snapshot to data/books_YYYYMMDDHH.jsonl.gz (a new file
each UTC hour) and logs to collector.log, including an hourly heartbeat
with the number of snapshots written.
"""
import gzip
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BOOKS_URL = "https://clob.polymarket.com/books"
INTERVAL = 2       # seconds between snapshots
CHUNK = 100        # tokens per request; lower it if the log shows missing books
LEVELS = 10        # price levels kept on each side of each book
DATA_DIR = "data"
UNIVERSE = "universe.json"

logging.basicConfig(filename="collector.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
session = requests.Session()


def load_tokens():
    with open(UNIVERSE) as f:
        u = json.load(f)
    return [m["yes_token"] for e in u["events"] for m in e["markets"]
            if not m.get("closed")]


def fetch(chunk):
    sent = time.time()
    r = session.post(BOOKS_URL, json=[{"token_id": t} for t in chunk], timeout=10)
    received = time.time()
    r.raise_for_status()
    books = r.json()
    if len(books) != len(chunk):
        logging.warning("requested %d books, received %d", len(chunk), len(books))
    return sent, received, books


def trim(book):
    """Sort each side best-first and keep the top LEVELS levels."""
    bids = sorted(book.get("bids", []), key=lambda x: float(x["price"]), reverse=True)
    asks = sorted(book.get("asks", []), key=lambda x: float(x["price"]))
    return {
        "token": book.get("asset_id"),
        "server_ts": book.get("timestamp"),
        "bids": [[float(b["price"]), float(b["size"])] for b in bids[:LEVELS]],
        "asks": [[float(a["price"]), float(a["size"])] for a in asks[:LEVELS]],
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    tokens = load_tokens()
    hour = time.strftime("%Y%m%d%H", time.gmtime())
    snapshots_this_hour = 0
    if snapshots_this_hour % 30 == 1:
            print(time.strftime("%H:%M:%S"), "snapshot written for", len(tokens), "tokens", flush=True)
    pool = ThreadPoolExecutor(max_workers=8)
    next_tick = time.time()
    logging.info("started with %d tokens", len(tokens))

    while True:
        now_hour = time.strftime("%Y%m%d%H", time.gmtime())
        if now_hour != hour:
            logging.info("heartbeat: %d snapshots in hour %s", snapshots_this_hour, hour)
            tokens = load_tokens()   # picks up any edits to universe.json
            hour, snapshots_this_hour = now_hour, 0

        chunks = [tokens[i:i + CHUNK] for i in range(0, len(tokens), CHUNK)]
        snapshot = {"tick": next_tick, "requests": []}
        # Send all chunks at the same moment so the legs are close in time.
        for fut in [pool.submit(fetch, c) for c in chunks]:
            try:
                sent, received, books = fut.result()
                snapshot["requests"].append({
                    "sent": sent, "received": received,
                    "books": [trim(b) for b in books],
                })
            except Exception as e:
                logging.warning("request failed: %s", e)

        with gzip.open(os.path.join(DATA_DIR, f"books_{hour}.jsonl.gz"), "at") as f:
            f.write(json.dumps(snapshot) + "\n")
        snapshots_this_hour += 1

        next_tick += INTERVAL
        if time.time() > next_tick + INTERVAL:   # fell behind; resync rather than burst
            logging.warning("fell behind schedule; resyncing")
            next_tick = time.time()
        time.sleep(max(0.0, next_tick - time.time()))


if __name__ == "__main__":
    main()
