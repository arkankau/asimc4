# v2 — INTARIAN_PEPPER_ROOT only

## Strategy summary
- **INTARIAN_PEPPER_ROOT**: Identical logic to v1. Always hold max long (80). Take all bot asks, post bid at best_bid+1 for remaining capacity. Never sells.
- **ASH_COATED_OSMIUM**: Not traded in this version.

## Backtest results
| Day | PEPPER P&L | Total |
|-----|-----------|-------|
| -2  |           |       |
| -1  |           |       |
|  0  |           |       |

## Live submission result
Round: 1
Submission ID: 237605
Platform P&L: 7,278 (×10 = ~72,780 real)
Notes: Perfectly linear uptrend. Platform shows 1/10th scale. Real P&L matches backtest (~79K). Concern: trend may not hold linearly in the actual final round test.
