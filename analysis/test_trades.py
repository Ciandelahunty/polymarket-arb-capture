"""Tests for paging through trades. Run with: pytest analysis"""
from trades import fetch_window


def fake_api(timestamps, page):
    """A stand-in for the trades endpoint: newest first, paged by offset."""
    def fetch(start, end, offset):
        inside = sorted((t for t in timestamps if start <= t <= end), reverse=True)
        return [{"timestamp": t} for t in inside[offset:offset + page]]
    return fetch


def test_small_window_is_fetched_in_one_go():
    ts = list(range(0, 10))
    got = fetch_window(fake_api(ts, 5), 0, 100, page=5, cap=20)
    assert sorted(t["timestamp"] for t in got) == ts


def test_busy_window_is_split_until_every_trade_is_fetched_once():
    ts = list(range(0, 1000))       # 1,000 trades, far above the cap of 20
    got = fetch_window(fake_api(ts, 5), 0, 999, page=5, cap=20)
    assert sorted(t["timestamp"] for t in got) == ts


def test_trades_at_the_split_point_are_not_lost_or_repeated():
    ts = [0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 8, 9]
    got = fetch_window(fake_api(ts, 2), 0, 9, page=2, cap=4)
    assert sorted(t["timestamp"] for t in got) == ts
