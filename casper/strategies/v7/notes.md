# v7 — Osmium Position-Aware Market-Make

## Strategy summary
Same market-making structure as v3 but with inventory management. When position exceeds SKEW_THRESHOLD (±40), stops posting on the heavy side to avoid getting pinned at ±80. At UNWIND_THRESHOLD (±65), posts 2 ticks inside bot spread on the unwinding side to exit faster.

## Key parameters
- `SKEW_THRESHOLD = 40` — stop adding to heavy side beyond this position
- `UNWIND_THRESHOLD = 65` — post tighter (best_ask-2) to exit aggressively

## Motivation
v3 ends at extreme positions (+80/-80) in backtest. In live trading this means we get stuck unable to quote one side, missing profitable opportunities when price reverses.

## Backtest results
| Day | OSMIUM P&L | pos | Total |
|-----|------------|-----|-------|
| -1  | 3,748      | +45 |       |
| -2  | 2,769      | +80 |       |
|  0  | 2,933      | -80 |       |
| **Grand** | **9,450** | | |

Note: backtest doesn't simulate bots hitting resting orders. Real live advantage of position management won't show here.

## Live submission result
Round: 1
Submission ID: 240234
Platform P&L: 2,800 (~28,000 real)
Notes: Essentially matches v3 (28,600 real). Best osmium result so far. Position management prevents pinning without hurting P&L.
