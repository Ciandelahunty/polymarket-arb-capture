"""Tests for turning a raw snapshot into table rows. Run with: pytest analysis"""
import pytest

from build_table import rows_for_snapshot

TICK = 1_758_600_000.0
YEAR = 365.25 * 86400


def snapshot(books):
    return {"tick": TICK, "requests": [{"sent": TICK, "received": TICK + 0.1, "books": books}]}


EVENT = {"slug": "e", "end_ts": TICK + YEAR, "tokens": ["a", "b"], "rates": [0.04, 0.04]}


def test_row_from_handmade_snapshot():
    books = [
        {"token": "a", "server_ts": str(int((TICK - 10) * 1000)),
         "bids": [[0.55, 1000]], "asks": [[0.60, 1000]]},
        {"token": "b", "server_ts": str(int((TICK - 2) * 1000)),
         "bids": [[0.35, 1000]], "asks": [[0.42, 1000]]},
    ]
    (row,) = rows_for_snapshot(snapshot(books), [EVENT])
    assert row["n_legs"] == 2 and row["n_present"] == 2
    assert row["t_years"] == pytest.approx(1.0)
    assert row["window_s"] == pytest.approx(0.1)
    assert row["age_min_s"] == pytest.approx(2.1)
    assert row["age_max_s"] == pytest.approx(10.1)
    assert row["buy_status_1"] == "ok"
    assert row["buy_price_1"] == pytest.approx(1.02)
    assert row["buy_fees_1"] == pytest.approx(0.04 * (0.60 * 0.40 + 0.42 * 0.58))
    assert row["sell_price_1"] == pytest.approx(0.90)
    assert row["buy_status_500"] == "ok"


def test_row_with_a_missing_leg():
    books = [{"token": "a", "server_ts": None, "bids": [[0.55, 1000]], "asks": [[0.60, 1000]]}]
    (row,) = rows_for_snapshot(snapshot(books), [EVENT])
    assert row["n_present"] == 1
    assert row["buy_status_1"] == "missing" and row["sell_status_1"] == "missing"
    assert row["buy_price_1"] is None
    assert row["age_min_s"] is None


# --- Closed legs -----------------------------------------------------------

THREE = {"slug": "e", "end_ts": TICK + YEAR, "tokens": ["a", "b", "c"],
         "rates": [0.0, 0.0, 0.0], "close_ts": [None, None, TICK - 60]}


def test_leg_closed_as_no_is_left_out_after_closing():
    books = [{"token": "a", "server_ts": None, "bids": [[0.55, 1000]], "asks": [[0.60, 1000]]},
             {"token": "b", "server_ts": None, "bids": [[0.35, 1000]], "asks": [[0.42, 1000]]}]
    (row,) = rows_for_snapshot(snapshot(books), [THREE])   # leg c closed a minute earlier, no book
    assert row["n_legs"] == 2 and row["n_present"] == 2
    assert row["buy_status_1"] == "ok"
    assert row["buy_price_1"] == pytest.approx(1.02)


def test_leg_is_still_required_before_it_closes():
    ev = dict(THREE, close_ts=[None, None, TICK + 60])     # closes a minute later
    books = [{"token": "a", "server_ts": None, "bids": [[0.55, 1000]], "asks": [[0.60, 1000]]},
             {"token": "b", "server_ts": None, "bids": [[0.35, 1000]], "asks": [[0.42, 1000]]}]
    (row,) = rows_for_snapshot(snapshot(books), [ev])
    assert row["n_legs"] == 3 and row["buy_status_1"] == "missing"
