# v1 — Baseline

## Strategy summary
- **INTARIAN_PEPPER_ROOT**: Always hold max long (80). Take all bot asks immediately, post bid at best_bid+1 for remaining capacity. Never sell. Exploits the ~+1000/day linear uptrend.
- **ASH_COATED_OSMIUM**: Market-make around fair value 10000. Post bid at best_bid+1 and ask at best_ask-1 (inside bot spread). Take any bot quotes that cross 10000 (rare).

## Backtest results (historical data)
| Day | PEPPER P&L | OSMIUM P&L | Total |
|-----|-----------|------------|-------|
| -2  | 79,592    | 2,736      | 82,328 |
| -1  | 79,249    | 3,935      | 83,184 |
|  0  | 79,400    | 3,061      | 82,461 |

## Live submission result
Round: 1
Submission ID: 235169
Platform P&L: 10,129 (×10 = ~101,290 real)
Notes: Confirmed = v2 + v3 (10,139 combined, diff of 10 is rounding noise). Assets are fully isolated — PEPPER and OSMIUM strategies do not interact. PEPPER dominates (~72% of P&L). Platform shows 1/10th scale.
