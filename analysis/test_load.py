"""Tests for reading raw files and fee rates. Run with: pytest analysis"""
import gzip
import json
from collections import Counter

from load import find_fee_rate, iter_snapshots, load_universe, server_seconds


def write_members(path, snapshots, truncate_index=None):
    with open(path, "wb") as f:
        for i, snap in enumerate(snapshots):
            member = gzip.compress((json.dumps(snap) + "\n").encode())
            if i == truncate_index:
                member = member[: len(member) // 2]   # simulate a write cut short
            f.write(member)


def test_reads_all_snapshots(tmp_path):
    p = tmp_path / "books.jsonl.gz"
    snaps = [{"tick": i, "requests": []} for i in range(5)]
    write_members(p, snaps)
    stats = Counter()
    assert [s["tick"] for s in iter_snapshots(p, stats)] == [0, 1, 2, 3, 4]
    assert stats["damaged_records"] == 0


def test_skips_a_damaged_record_and_keeps_the_rest(tmp_path):
    p = tmp_path / "books.jsonl.gz"
    snaps = [{"tick": i, "requests": [], "pad": "x" * 500} for i in range(5)]
    write_members(p, snaps, truncate_index=2)
    stats = Counter()
    ticks = [s["tick"] for s in iter_snapshots(p, stats)]
    assert ticks == [0, 1, 3, 4]
    assert stats["damaged_records"] >= 1


def test_find_fee_rate_variants():
    assert find_fee_rate({"feeSchedule": {"rate": 0.05}})[0] == 0.05
    assert find_fee_rate({"feeSchedule": {"makerRate": 0, "takerRate": 0.04}})[0] == 0.04
    assert find_fee_rate({"makerBaseFee": 0, "takerBaseFee": 0})[0] is None
    assert find_fee_rate({"feeRateEnabled": True})[0] is None
    assert find_fee_rate({"feeSchedule": {"rate": "0.04"}})[0] == 0.04


def test_server_seconds_handles_milliseconds():
    assert server_seconds("1758600000000") == 1758600000.0
    assert server_seconds(1758600000) == 1758600000.0
    assert server_seconds(None) is None


def test_markets_with_fees_disabled_are_fee_free(tmp_path):
    universe = {"events": [{
        "slug": "no-fee-event", "end_date": "2026-11-03T12:00:00Z", "fees": {},
        "markets": [
            {"label": "A", "yes_token": "1", "closed": False,
             "fees": {"feesEnabled": False, "feeType": None}},
            {"label": "B", "yes_token": "2", "closed": False,
             "fees": {"feesEnabled": False, "feeType": None}},
        ],
    }]}
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(universe))
    (event,) = load_universe(p)
    assert event["rates"] == [0.0, 0.0]
    assert event["rate_sources"][0] == "feesEnabled=false"
