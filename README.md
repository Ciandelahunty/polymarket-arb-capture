# Arbitrage Analysis on Polymarket: Visible vs Capturable

In the most liquid established markets, high-frequency trading firms keep related prices consistent with each other, so obvious mispricings last milliseconds. Prediction markets such as Polymarket are younger and much smaller, and the consistency of prices is less clear. Polymarket's CEO, Shayne Coplan, has called it a "global truth machine" ([The Economist, 10 Sept 2026]), and its prices are increasingly read as forecasts of elections, inflation and central bank decisions. In order for these forecasts to be accurate, prices within each event must remain consistent. This project tests this consistency: in an event where exactly one outcome wins, the prices of all outcomes should sum to about $1. Earlier studies count how often this rule breaks at the best quoted prices. Here I additionally test whether anyone could actually profit from the breaks after fees, order book depth and reaction time, and who, if anyone, trades against them.

A bot records the full order book of every outcome in 20 Polymarket events every 2 seconds, and a pricing pipeline works out what each basket would have cost to trade at 1, 100 and 500 baskets.

> **Collection ended on 7 Oct 2026 at 12:50 UTC.** The results below are from 637,760 snapshots over 14.8 days (22 Sept – 7 Oct 2026).

## Findings

| | |
| --- | --- |
| Event-snapshots in which the buy-side bound was violated, at the best prices | **1.2%** |
| Violation episodes that survived at 100 baskets | **0.8%** (11 of 1,387) |
| Violation episodes that survived at 500 baskets | **0.07%** (1 of 1,387) |
| Sell-side violations | **2 episodes** of a few seconds each, at most 5 baskets |
| Profit of a paper-trading bot reacting 2 seconds late | **$12.22** |

1. **The no-arbitrage bound almost always holds, by a wide margin.** Buying one basket at the best available prices typically costs 12.8¢ more than its fair value; selling one typically raises 10.4¢ less than $1. The margin is the combined bid–ask spread across every outcome, plus fees, and it grows quickly with size: at 500 baskets the typical buy-side margin is 60¢.
2. **Violations are common at the best prices but rarely survive a realistic trade.** Buy-side violations appeared in 1.2% of event-snapshots, in 1,387 separate episodes lasting a median of 2–6 seconds. Only 11 ever reached a violation at 100 baskets, and 1 at 500.
3. **The sell-side bound was broken only once,** across 12.8 million event-snapshots. Selling the basket can be turned into cash immediately, so it is the easiest direction to arbitrage and was predicted to be policed hardest. The one break came when a program placed 5-share bids at 2¢ on every bucket of a 46-outcome market, so that the bids added up to more than $1; a trader sold into them within seconds.
4. **Most violations disappear without anyone trading.** 1,343 of 1,387 buy-side episodes ended with no trades in the direction that would capture them; the quotes simply moved. In 27 episodes a single trader bought every outcome within 60 seconds, capturing the basket. Across all episodes there were 870 trades in the capturing direction, against 92 expected at the events' normal trading rates: violations are rarely traded, but when they are, the trading is concentrated on them.
5. **The longest violations are too small to be worth tying money up for.** They occur mainly in a market that resolves in about 15 months; its longest episode lasted at least 33 hours. Its basket usually prices at an implied return of about 1.5–3.5% a year, below the 4.11% Treasury bill rate, and for stretches it priced a little above it. Those stretches are the long violations: at a 5.11% discount rate, violations at 500 baskets fall from 544 event-snapshots to 20.

### Example: an arbitrage captured in two seconds

On 26 Sept at 12:28:32 UTC, in the *China annual inflation* market, a 20-share offer on the most likely outcome appeared 10¢ below the usual price, taking the basket 15.4¢ below its fair value. In the next snapshot every one of the nine outcomes had lost exactly 18 shares: someone had bought 18 complete baskets, the most the thinnest outcome's order book allowed, for roughly $2.80 of profit. The same basket had been 5.2¢ below fair value for over a minute beforehand, and nobody had taken it.

## How it works

**The no-arbitrage rule.** In a Polymarket *negRisk* event, the outcomes are mutually exclusive, and exactly one wins. A *basket* of one YES share on every outcome therefore pays exactly $1. Two violations are possible:

- **Buy side:** buying the basket for less than $1, discounted to today (the $1 arrives only when the event resolves).
- **Sell side:** selling the basket (buying NO on every outcome) for more than $1. In a negRisk event these NO shares convert into cash immediately, so no discounting applies.

**Data.** 20 negRisk events across US midterm elections, inflation and central-bank decisions, a UK by-election and other topics, chosen to span heavily and barely traded markets. A collector on a rented Linux server requests the order book of every outcome (186 markets) in one batch every 2 seconds, keeping enough price levels to price 1,000 shares.

**Pricing.** For each snapshot, event and size (1, 100 and 500 baskets), the pipeline:

1. walks each outcome's order book to find what that many shares actually cost;
2. adds each market's taker fee, charged per share as rate × p × (1 − p);
3. compares the total with the bound, discounting the buy side at the 13-week US Treasury bill rate (4.11%) to each event's end date, less any holding reward Polymarket pays.

**Measures.**

- **Gap:** distance from the bound, in cents per basket. Negative means a violation.
- **Episode:** a run of consecutive snapshots in violation. Durations are reported as lower and upper bounds, because a violation can start or end between snapshots.
- **Capture rate:** the share of episodes visible at 1 basket that also reach a violation at 100 or 500.
- **Paper-trading bot:** on first seeing a violation, it trades at the next snapshot's prices, all or nothing. This measures what reacting 2 seconds late costs.
- **Trade history:** public trades around each episode show whether it ended because someone traded against it or because quotes moved.

**Pre-registration.** Definitions were fixed in [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md) and committed before any results were computed. Every later change is listed there as a deviation, with its reason and whether it came after seeing results.

## Robustness checks

- **Discount rate:** results at 0%, 3.11%, 4.11% and 5.11%, and with each event discounted at the Treasury yield matching its time to resolution. The main effect of horizon-matching is fewer long violations in the 15-month market (size-500 violations fall from 544 snapshots to 307); other results barely change.
- **Staleness:** all outcomes of an event are read within a median 0.10 seconds of each other. Results are shown with and without the 0.02% of snapshots taking longer than 1 second.
- **Data quality:** order book timestamps never ran backwards, confirming no stale responses in the periods checked.

## Limitations

- **Only taker trades are measured.** The data shows which orders could be traded against, not whether a posted order would have filled. Makers pay no fee and can earn liquidity rewards, which this study does not model.
- **Violations shorter than 2 seconds are not observed.** Published work on Polymarket finds median durations of a few seconds in fast markets.
- **The paper bot assumes every outcome fills at once.** A real bot would trade outcomes one after another and could be left partly filled.
- **The sample is small and correlated.** 20 events, about nine tied to the US midterms, and two events account for almost all buy-side violations.
- **One event is not strictly exhaustive.** China inflation's outcomes miss exactly −1.0%; the effect on its bound is under 1¢.
- **Outcomes that closed during collection** (Musk tweet-count buckets settled as No once the count passed them) are left out of their event's basket from their closing time. The basket of the remaining outcomes still pays exactly $1.

## Repository

```
ANALYSIS_PLAN.md        definitions fixed in advance, deviations, verified checks
slugs.txt               the 20 events
universe.py             builds universe.json from Polymarket's API: markets, fees, end dates
universe.json           the sample as recorded at the start of collection
collector.py            the order book collector
collector.service       runs the collector as a service on a Linux server
analysis/
  settings.py           parameters: sizes, discount rates, cutoffs, holding reward
  costs.py              fees, book walking, basket pricing, discounting
  load.py               reading raw snapshots, event data and processed tables
  build_table.py        raw snapshots -> hourly tables
  checks.py             data quality report
  episodes.py           violation episodes and duration bounds
  trades.py             downloads public trades for the collection period
  results.py            results, robustness checks, paper-trading bot, trade history
  closed_legs.py        records outcomes that closed during collection (closed_legs.json)
  inspect_event.py      one event's order books over a short period
  test_*.py             66 unit tests (pytest analysis)
```

Raw data (15 GB compressed) is not included.

## Running it

```
pip install -r requirements.txt -r analysis/requirements.txt
python universe.py                    # build the sample
python collector.py                   # collect (runs until stopped)
pytest analysis                       # run the tests
python analysis/closed_legs.py        # record outcomes that have closed
python analysis/build_table.py        # process new raw files (--force after closed_legs.json changes)
python analysis/trades.py             # download trades for the period
python analysis/results.py            # results, charts and tables
```

## Related work

- [Executable arbitrage and market efficiency in prediction markets](https://arxiv.org/html/2608.00666) (2026): depth-aware arbitrage in Polymarket negRisk markets.
- [Arbitrage analysis in Polymarket NBA markets](https://arxiv.org/abs/2605.00864) (2026): violations lasting a median 3.6 seconds, mostly limited to a few shares.
- [Capital lock-up and settlement discounting in prediction markets](https://arxiv.org/pdf/2605.31431) (2026): why long-dated contracts trade below $1.
- (https://www.economist.com/graphic-detail/2026/09/10/where-prediction-markets-struggle)
