# root-cap — Root with Ask Price Cap

## Strategy summary
Same as root-maxlong but refuses to buy any ask more than `MAX_SPREAD` (5 ticks) above the current best bid. Prevents bleeding on outlier high asks while still accumulating on normal prices.

## Key parameters
- `MAX_SPREAD = 5` — max ticks above best bid willing to pay

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
