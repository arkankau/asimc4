# v8 — Osmium Extreme Reversion

## Strategy summary
Combines v3 market-making with directional contra-trend bets at price extremes. When |mid - 10000| < 10: normal symmetric market-make. When |mid - 10000| >= 10: tilt heavily toward the contra side (tighter resting order, skew position limit). Directly implements the "tipping the scale" advisor hint.

## Key parameters
- `EXTREME_THRESHOLD = 10` — deviation from 10000 to enter extreme mode
- `SKEW_THRESHOLD = 40` — don't add more inventory on heavy side beyond this

## Data backing
- At ±10 deviation: 74.9% chance of reversion next tick, avg return -4.3/+4.7
- At ±15 deviation: 95% chance of reversion next tick, avg return -7.1/+7.6

## Backtest results
| Day | OSMIUM P&L | pos | Total |
|-----|------------|-----|-------|
| -1  | 3,748      | +45 |       |
| -2  | 2,769      | +80 |       |
|  0  | 2,933      | -80 |       |
| **Grand** | **9,450** | | |

Note: tighter resting orders and skewed quoting at extremes won't show in backtest — only live testing distinguishes this from v7.

## Live submission result
Round: 1
Submission ID: 240131
Platform P&L: 2,776 (~27,760 real)
Notes: Slightly below v3 (28,600 real). Curve noisier/more active than v3 — extreme reversion logic fires frequently. The tighter asks at extremes are getting filled but not generating enough extra edge to beat baseline.
