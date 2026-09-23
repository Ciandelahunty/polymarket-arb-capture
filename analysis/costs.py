"""Core calculations: fees, walking the book, baskets, discounting and gaps.

Pure arithmetic with no file access, so every function can be unit-tested
directly (see test_costs.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from settings import RECORDED_LEVELS

# Status of a fill, for one leg or a whole basket.
OK = "ok"
TRUNCATED = "truncated"    # recorded levels ran out, but the real book may continue beyond them
UNFILLABLE = "unfillable"  # the whole side of the book was recorded and it has too few shares
MISSING = "missing"        # the leg's book is absent from the snapshot

# A basket takes the status of its worst leg.
_SEVERITY = {OK: 0, TRUNCATED: 1, UNFILLABLE: 2, MISSING: 3}

SECONDS_PER_YEAR = 365.25 * 86400


def fee_per_share(price, rate):
    """Polymarket taker fee per share: rate x p x (1 - p)."""
    return rate * price * (1.0 - price)


@dataclass
class Fill:
    status: str
    notional: float | None = None   # sum of price x shares taken
    fees: float | None = None


def walk_book(levels, qty, rate, recorded_levels=RECORDED_LEVELS):
    """Take `qty` shares from `levels`, a list of [price, size] with the best
    price first. On asks this is the cost of buying; on bids, the proceeds of
    selling. The fee is charged on the shares taken at each level's price.
    """
    remaining = qty
    notional = fees = 0.0
    for price, size in levels:
        take = min(remaining, size)
        notional += take * price
        fees += take * fee_per_share(price, rate)
        remaining -= take
        if remaining <= 1e-9:
            return Fill(OK, notional, fees)
    if len(levels) >= recorded_levels:
        return Fill(TRUNCATED)
    return Fill(UNFILLABLE)


def worst_status(statuses):
    return max(statuses, key=_SEVERITY.__getitem__, default=MISSING)


def basket(books, rates, qty, side):
    """Fill `qty` baskets across all legs.

    side="buy" walks each leg's asks (buying YES on every outcome);
    side="sell" walks each leg's bids (selling YES on every outcome, which is
    the same trade as buying NO on every outcome).

    `books` has one entry per leg: a dict with "bids" and "asks", or None if
    the leg is missing. Returns (status, price per basket before fees,
    fees per basket); the last two are None unless status is OK.
    """
    key = "asks" if side == "buy" else "bids"
    statuses, notional, fees = [], 0.0, 0.0
    for book, rate in zip(books, rates):
        if book is None:
            statuses.append(MISSING)
            continue
        fill = walk_book(book[key], qty, rate)
        statuses.append(fill.status)
        if fill.status == OK:
            notional += fill.notional
            fees += fill.fees
    status = worst_status(statuses)
    if status != OK:
        return status, None, None
    return OK, notional / qty, fees / qty


def years_between(t0, t1):
    return max(0.0, (t1 - t0) / SECONDS_PER_YEAR)


def discount_factor(r, t_years):
    """Present value of $1 paid in t_years at annual rate r."""
    return (1.0 + r) ** (-t_years)


def buy_gap(price, fees, df):
    """Buying the basket: cost including fees minus the discounted $1 it pays.
    Negative means a violation."""
    return price + fees - df


def sell_gap(price, fees):
    """Selling the basket: $1 minus proceeds after fees. Not discounted,
    because in a negRisk event the NO positions convert into cash
    immediately. Negative means a violation."""
    return 1.0 - (price - fees)
