# v5 — Root with Rolling Slope + Hysteresis

## Strategy summary
Tracks mid-prices via `traderData`. Computes linear regression slope over a long window. Holds max long while slope >= `SLOPE_MIN`. Only unwinds after slope stays weak for `CONFIRM_TICKS` consecutive ticks (hysteresis guard), preventing false exits on short noise.

## Key parameters
- `WINDOW = 150` — long window smooths intra-trend noise
- `SLOPE_MIN = 0.01` — minimum slope to stay long
- `CONFIRM_TICKS = 30` — consecutive weak-slope ticks required before unwind triggers

## v1 attempt post-mortem (WINDOW=20, SLOPE_MIN=0.02, no hysteresis)
Platform P&L: ~-5,500 (~-55,000 real). Catastrophic false-unwind loop.
- WINDOW=20 is too short: price noise within 20 ticks repeatedly made slope go negative mid-uptrend
- No hysteresis: every brief dip triggered a full unwind + re-accumulate, bleeding spread each round-trip
- Sawtooth P&L chart is the signature of this failure mode

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
