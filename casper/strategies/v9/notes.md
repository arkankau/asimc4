# v9 — Combined Best (v5.2 root + v3 osmium)

## Strategy summary
- **IPR**: v5.2 slope gate with hysteresis — max long while slope >= 0.01 over 150-tick window, unwinds only after 30 consecutive weak ticks.
- **ACO**: v3 market-make — 1 tick inside bot spread around FV 10000, takes any cross-FV quotes.

## Backtest results
| Day | IPR P&L | ACO P&L | Total |
|-----|---------|---------|-------|
| -1  | 79,249  | 3,935   | 83,184 |
| -2  | 79,592  | 2,736   | 82,328 |
|  0  | 79,400  | 3,061   | 82,461 |
| **Grand** | **238,241** | **9,732** | **247,973** |

## Live submission result
Round: 1
Submission ID: 241729
Platform P&L: 10,129 (~101,290 real)
IPR: 7,286 | ACO: 2,843
Notes: Matches v1 exactly. Safety net never triggered (trend clean). Best combined strategy.
