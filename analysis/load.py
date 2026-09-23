"""Reading the collector's raw files and universe.json."""
import json
import zlib
from datetime import datetime

from settings import UNIVERSE

GZIP_MAGIC = b"\x1f\x8b\x08"
_BLOCK = 1 << 16

# If a market's fee rate can't be found automatically, set it here by event
# slug, e.g. {"china-annual-inflation-2026": 0.05}.
FEE_OVERRIDES = {}


def _gzip_members(data, stats):
    """Yield the decompressed contents of each gzip member in `data`.

    The collector writes one member per snapshot. If the collector is stopped
    mid-write, one member can be cut short; this skips it and carries on from
    the next member instead of losing the rest of the file.
    """
    mv = memoryview(data)
    n, pos = len(data), 0
    while pos < n:
        d = zlib.decompressobj(wbits=31)
        out, p, ok = [], pos, True
        try:
            while not d.eof and p < n:
                chunk = mv[p:p + _BLOCK]
                out.append(d.decompress(chunk))
                p += len(chunk)
        except zlib.error:
            ok = False
        if ok and d.eof:
            yield b"".join(out)
            pos = p - len(d.unused_data)
        else:
            stats["damaged_records"] += 1
            nxt = data.find(GZIP_MAGIC, pos + 1)
            if nxt == -1:
                return
            pos = nxt


def iter_snapshots(path, stats):
    """Yield each snapshot (a dict) from one raw data file."""
    with open(path, "rb") as f:
        data = f.read()
    for member in _gzip_members(data, stats):
        for line in member.split(b"\n"):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                stats["damaged_records"] += 1


def server_seconds(ts):
    """Polymarket book timestamps, converted to seconds (they may be in ms)."""
    if ts is None:
        return None
    try:
        v = float(ts)
    except (TypeError, ValueError):
        return None
    return v / 1000.0 if v > 1e11 else v


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def find_fee_rate(fees):
    """Find the taker fee rate among a market's fee fields.

    Looks for numeric values under keys containing "rate", preferring a key
    containing "taker", then a key named exactly "rate". Returns
    (rate, where it was found) or (None, None).
    """
    candidates = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif not isinstance(obj, bool):
            key = path.rsplit(".", 1)[-1].lower()
            if "rate" in key:
                try:
                    candidates.append((path, key, float(obj)))
                except (TypeError, ValueError):
                    pass

    walk(fees or {}, "")
    for prefer in (lambda k: "taker" in k, lambda k: k == "rate", lambda k: True):
        for path, key, val in candidates:
            if prefer(key) and 0.0 <= val <= 0.2:
                return val, path
    return None, None


def fees_disabled(fees):
    """True if Polymarket marks the market as having fees switched off."""
    return isinstance(fees, dict) and fees.get("feesEnabled") is False


def load_universe(path=UNIVERSE):
    """Return one dict per event: slug, end time, and the YES token and fee
    rate of each open leg, in the same order the collector uses."""
    with open(path) as f:
        u = json.load(f)
    events, problems = [], []
    for e in u["events"]:
        slug = e["slug"]
        legs = [m for m in e["markets"] if not m.get("closed")]
        rates, sources = [], []
        for m in legs:
            if slug in FEE_OVERRIDES:
                rate, src = FEE_OVERRIDES[slug], "override"
            elif fees_disabled(m.get("fees")):
                rate, src = 0.0, "feesEnabled=false"
            else:
                rate, src = find_fee_rate(m.get("fees"))
                if rate is None:
                    rate, src = find_fee_rate(e.get("fees"))
                    src = f"event.{src}" if src else None
            if rate is None:
                problems.append(f"{slug}: no fee rate found for '{m.get('label')}'")
            rates.append(rate)
            sources.append(src)
        if not e.get("end_date"):
            problems.append(f"{slug}: no end date")
        events.append({
            "slug": slug,
            "end_ts": parse_time(e["end_date"]) if e.get("end_date") else None,
            "tokens": [m["yes_token"] for m in legs],
            "labels": [m.get("label") for m in legs],
            "rates": rates,
            "rate_sources": sources,
        })
    if problems:
        raise SystemExit("Fix these in universe.json or FEE_OVERRIDES in load.py:\n  "
                         + "\n  ".join(dict.fromkeys(problems)))
    return events
