# v3 — ASH_COATED_OSMIUM only

## Strategy summary
- **INTARIAN_PEPPER_ROOT**: Not traded in this version.
- **ASH_COATED_OSMIUM**: Identical logic to v1. Market-make around fair value 10000. Post bid at best_bid+1 and ask at best_ask-1 (inside bot spread). Take any bot quotes that cross 10000.

## Backtest results
| Day | OSMIUM P&L | Total |
|-----|------------|-------|
| -2  |            |       |
| -1  |            |       |
|  0  |            |       |

## Live submission result
Round: 1
Submission ID: 237934
Platform P&L: 2,861 (×10 = ~28,600 real)
Notes: Noisy but steady upward curve. Market-making collecting spread consistently throughout the round.
