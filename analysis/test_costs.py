"""Unit tests for the core calculations. Run from the repository folder:
    pytest analysis
"""
import pytest

from costs import (MISSING, OK, TRUNCATED, UNFILLABLE, basket, buy_gap,
                   discount_factor, fee_per_share, sell_gap, walk_book)


# --- Fees ---------------------------------------------------------------

def test_fee_matches_worked_example():
    # 100 shares at $0.50 with rate 0.04 should cost $1.00 in fees.
    assert 100 * fee_per_share(0.50, 0.04) == pytest.approx(1.00)


def test_fee_is_symmetric_and_zero_at_the_ends():
    assert fee_per_share(0.2, 0.04) == pytest.approx(fee_per_share(0.8, 0.04))
    assert fee_per_share(0.0, 0.04) == 0
    assert fee_per_share(1.0, 0.04) == 0


# --- Walking the book ---------------------------------------------------

ASKS = [[0.30, 500], [0.31, 800], [0.34, 2000]]


def test_walk_within_first_level():
    f = walk_book(ASKS, 200, rate=0.0)
    assert f.status == OK
    assert f.notional == pytest.approx(200 * 0.30)


def test_walk_across_levels_matches_notes_example():
    # 1,000 shares: 500 at $0.30 and 500 at $0.31, averaging $0.305.
    f = walk_book(ASKS, 1000, rate=0.0)
    assert f.notional / 1000 == pytest.approx(0.305)


def test_walk_charges_fee_at_each_level():
    f = walk_book(ASKS, 1000, rate=0.04)
    expected = 500 * 0.04 * 0.30 * 0.70 + 500 * 0.04 * 0.31 * 0.69
    assert f.fees == pytest.approx(expected)


def test_walk_exactly_exhausting_the_book_is_ok():
    assert walk_book(ASKS, 3300, rate=0.0).status == OK


def test_short_book_fully_recorded_is_unfillable():
    assert walk_book(ASKS, 5000, rate=0.0).status == UNFILLABLE


def test_short_book_at_recording_limit_is_truncated():
    ten_levels = [[0.30 + 0.01 * i, 10] for i in range(10)]
    assert walk_book(ten_levels, 500, rate=0.0).status == TRUNCATED


def test_empty_side_is_unfillable():
    assert walk_book([], 1, rate=0.0).status == UNFILLABLE


# --- Baskets ------------------------------------------------------------

def book(asks=(), bids=()):
    return {"asks": [list(x) for x in asks], "bids": [list(x) for x in bids]}


def test_buy_basket_sums_legs_and_divides_by_size():
    books = [book(asks=[(0.58, 1000)]), book(asks=[(0.24, 1000)]), book(asks=[(0.12, 1000)])]
    status, price, fees = basket(books, [0.04] * 3, 100, "buy")
    assert status == OK
    assert price == pytest.approx(0.94)
    assert fees == pytest.approx(0.04 * (0.58 * 0.42 + 0.24 * 0.76 + 0.12 * 0.88))


def test_missing_leg_makes_basket_missing():
    books = [book(asks=[(0.5, 100)]), None]
    assert basket(books, [0.04] * 2, 1, "buy")[0] == MISSING


def test_basket_takes_worst_leg_status():
    ten = [[0.1, 1]] * 10
    books = [book(asks=ten), book(asks=[(0.5, 1)])]
    # One leg truncated, one unfillable: unfillable is worse.
    assert basket(books, [0.0] * 2, 50, "buy")[0] == UNFILLABLE
    books = [book(asks=ten), book(asks=[(0.5, 100)])]
    assert basket(books, [0.0] * 2, 50, "buy")[0] == TRUNCATED


def test_sell_basket_walks_bids():
    books = [book(bids=[(0.60, 50), (0.59, 100)]), book(bids=[(0.45, 200)])]
    status, price, fees = basket(books, [0.0] * 2, 100, "sell")
    assert status == OK
    assert price == pytest.approx((50 * 0.60 + 50 * 0.59) / 100 + 0.45)


# --- Discounting and gaps -----------------------------------------------

def test_discount_factor():
    assert discount_factor(0.04, 0) == 1
    assert discount_factor(0.0, 3) == 1
    assert discount_factor(0.04, 1) == pytest.approx(1 / 1.04)


def test_buy_gap_matches_worked_example():
    # Asks 0.58, 0.24, 0.12; fee rate 0.04; three months to resolution; r = 4%.
    fees = sum(fee_per_share(p, 0.04) for p in (0.58, 0.24, 0.12))
    gap = buy_gap(0.94, fees, discount_factor(0.04, 0.25))
    assert gap == pytest.approx(-0.029, abs=0.0005)


def test_sell_gap_sign():
    assert sell_gap(1.03, 0.01) == pytest.approx(-0.02)   # violation
    assert sell_gap(0.97, 0.01) > 0                        # no violation
