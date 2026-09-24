# Analysis plan

Written and committed before any gaps were computed from the collected data. Any later change is listed under **Deviations** with the reason, and results at interim points are labelled preliminary and produced with the same code.

## Data

- **Sample:** 20 negRisk events (not augmented) listed in `slugs.txt`; the markets and their state at the start are in `universe.json`.
- **Collection:** order books for the YES token of every open outcome, top 10 price levels per side, polled every 2 seconds from 22 September 2026 (~17:15 UTC) on a server in Helsinki.
- **Settings** used by the code are in `analysis/settings.py` and match this document.

## Definitions

**Basket.** One YES share on every open outcome of an event. Exactly one outcome wins, so a basket pays $1 at resolution.

**Basket size.** Number of baskets traded: **1** (the best available prices, i.e. the violation that is visible), **100**, and **500** (roughly $500 of notional, a realistic small trade). Sizes were chosen in advance so results can't be tuned by choosing the size afterwards.

**Buy side.** Buy the basket by walking each leg's asks for the chosen size and paying the taker fee on each level. Positions are held until resolution, so the $1 payout is discounted.
- `buy_gap = price per basket + fees per basket − 1/(1 + r)^t`

**Sell side.** Sell the basket by walking each leg's bids (equivalent to buying NO on every outcome), paying the taker fee. In a negRisk event, NO on all N outcomes converts immediately into N − 1 dollars, so no discounting applies.
- `sell_gap = 1 − (price per basket − fees per basket)`

**Violation.** A gap below zero, for a given side and size.

**Fees.** Each market's own taker rate from Polymarket's data, applied per share at each price level walked: `rate × p × (1 − p)`. Every trade is assumed to take orders already in the book (a taker trade). The snapshots show which orders were available to trade against, but not whether an order posted and left waiting would have been filled, so taker execution is the only kind this data can measure. It is also the conservative choice, since makers pay no fee.

**Discounting.** `r` is the 13-week US Treasury bill yield on 22 September 2026, the latest published when this plan was written: 4.11% on a coupon-equivalent basis (the annualised return on the price paid). `t` is the time from the snapshot to the event's end date in `universe.json`, in years. Buy-side results are also reported at r = 0 and at r ± 1 percentage point.

**Complete basket.** Every open outcome's book is present in the snapshot. If any is missing (for example because a request failed), the basket is **missing** at every size for that snapshot, never a violation.

**Recorded depth.** Only the top 10 price levels of each book are stored. If the recorded levels hold too few shares for a size:
- fewer than 10 levels were recorded → the whole side of the book was seen, and the basket is **unfillable** at that size;
- exactly 10 levels were recorded → the book may continue beyond them, and the basket is **truncated** (unknown) at that size.

**Staleness.** For each event and snapshot, the time between the earliest request sent and the latest response received among the requests carrying its legs. Results are reported for all snapshots and for snapshots with staleness of 1 second or less.

**Violation episode.** A run of consecutive snapshots with a gap below zero, for a given event, side and size. A missing or incomplete snapshot is treated as unknown: it neither ends nor extends an episode, and episodes interrupted this way are marked censored.

## Results to report

1. **The gap:** its distribution for each side and size, overall and by event.
2. **Frequency:** share of complete snapshots in violation, by side and size.
3. **Survival:** distribution of episode durations, with censored episodes handled explicitly.
4. **Capture rate:** share of violations visible at size 1 that remain violations at size 500 after fees.
5. **Attention:** whether violation frequency and duration relate to event volume.

## Robustness

- Discount rate sensitivity (buy side).
- Staleness cutoff on and off.
- Truncated baskets reported separately rather than dropped silently.

## Known collection events

- **23 Sept 2026, 06:25–06:26 UTC:** the collector was restarted several times by automatic system updates, pausing collection for roughly 30 seconds in total. Snapshots written as the collector was stopped may be damaged; the loader skips damaged records and reports how many.
- **23 Sept 2026, 19:15 to 21:08 UTC:** the collector polled every 5 seconds instead of 2, because the updated collector file reverted the interval setting. Snapshots from this period are kept and analysed like all others, since survival measures use actual timestamps.

## Verified

- **Conversion fee (23 Sept 2026).** The sell-side calculation assumes that converting NO positions on every outcome into cash carries no fee. Checked by reading `getFeeBips` on the Neg Risk Adapter contract (`0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296`) via Polygonscan for three of the sampled events, using each event's negRisk market ID. All three returned 0.
- **Discount rate.** Taken from the US Treasury's published daily bill rates for 22 Sept 2026, coupon-equivalent basis.

## Deviations

All changes below followed the first pipeline test on 23 Sept 2026, which checked data quality on the first 25 hours. No survival, capture-rate or attention analysis had yet been run.

1. **Sell-side shortfalls valued at zero.** If an outcome's bids can't fill the full size, the unfilled shares are now valued at a price of zero instead of making the basket unfillable. This is achievable without trading those shares: buying NO on the other outcomes and converting them yields cash plus a YES on the thin outcome, so the profit is at least the sum of the bids filled minus $1. It only applies when the whole side of the book was recorded; a side that was cut short is still treated as truncated. Before this change, four events had no sell-side result because one outcome had no bids at all.

2. **Deeper order books recorded from 19:15 UTC, 23 Sept 2026.** In the first test, 57% of buy baskets at size 500 were truncated under the 10-level limit. The collector now keeps at least 10 levels per side and continues until 1,000 shares are covered, and records whether any levels were left out. Snapshots before this time keep the original rule (a side with exactly 10 recorded levels is treated as possibly cut).

3. **Episode details (written before any episode results were computed)**

- Snapshots more than 12 seconds apart are treated as having missing data between them (the collector polls every 2 seconds, or 5 during the 23 Sept incident).
- Snapshots at or after an event's end date are treated as unknown, since the event may be resolving.
- Episode durations are now reported as bounds: the lower bound is the time between the first and last snapshots including a violation; the upper bound is the time between the last clean snapshot and the first clean snapshot after, and is only given when neither end is censored.

4. **Additions to the results (after seeing the preliminary episode summary on 24 Sept).**

- A paper-trading bot: on first seeing a violation at size 1, it tries to trade at the next snapshot at that snapshot's prices, all or nothing, and records the profit. It measures the cost of reacting one snapshot late.
- Capture rate is also reported per episode (whether an episode ever reaches a violation at the larger size), alongside the per-snapshot measure in the plan.
- For attention, volume is the 24-hour volume in universe.json at the start of collection. Two more measures are reported alongside it: the median quote age of each event's stalest leg, and each event's number of outcomes.
