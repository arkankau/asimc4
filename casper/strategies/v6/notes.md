# root-trailing — Root with Trailing Drawdown Stop

## Strategy summary
Tracks the running peak mid-price via `traderData`. While the price stays within `DRAWDOWN` (30 ticks) of its all-time peak, holds max long normally. If price falls 30+ ticks below peak, triggers a full unwind: sells all holdings into bids and posts a passive ask for the remainder.

## Key parameters
- `DRAWDOWN = 30` — ticks below peak mid that triggers the unwind

## Backtest results
| Day | PEPPER P&L | Total |
|-----|-----------|-------|
| -2  |           |       |
| -1  |           |       |
|  0  |           |       |

## Live submission result
Round: 
Score: 
Notes: 
