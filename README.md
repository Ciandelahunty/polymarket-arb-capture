# polymarket-arb-capture
A bot that monitors 20 mutually exclusive Polymarket events for no-arbitrage violations and measures what fraction could be captured after fees, depth and latency.

Interim results so far (28 Sept)
- 244,924 snapshots of 20 events over 5.7 days, 22 Sept 17:18 to 28 Sept 10:32 UTC.
- Across 245,000 snapshots of 20 negRisk events, the sell-side bound was never violated. Buy-side violations appeared in 2.7% of snapshots at the best prices, but only 1.6% of episodes survived at 100 baskets and 0.2% at 500. A bot reacting 2 seconds late would have made $7.57.

