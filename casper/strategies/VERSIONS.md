# Strategy Versions

| Version | File | Round | Description | Backtest P&L/day | Live Score |
|---------|------|-------|-------------|-----------------|------------|
| [v1](v1/notes.md) | `combined_baseline.py` | 1 | Both products: PEPPER trend-follow + OSMIUM market-make | ~82K | 10,129 (~101,290 real) |
| [v2](v2/notes.md) | `root_maxlong.py` | 1 | PEPPER only, always max long, no safeguards | *(pending)* | 7,278 (~72,780 real) |
| [v3](v3/notes.md) | `osmium_marketmake.py` | 1 | OSMIUM only, market-make around FV 10000 | *(pending)* | 2,861 (~28,600 real) |
| [v4](v4/notes.md) | `root_cap.py` | 1 | PEPPER + ask price cap (≤ best_bid+5) | *(pending)* | *(pending)* |
| [v5](v5/notes.md) | `root_slope.py` | 1 | PEPPER + rolling slope gate (unwind when trend lost) — v5 bad, see v5.2 | *(pending)* | *(pending)* |
| [v5.2](v5.2/notes.md) | `root_slope.py` | 1 | PEPPER + slope gate with hysteresis (WINDOW=150, CONFIRM=30) | ~79,400/day | 7,578 (~75,780 real) |
| [v6](v6/notes.md) | `root_trailing.py` | 1 | PEPPER + trailing drawdown stop (unwind if -30 from peak) | *(pending)* | 7,286 (~72,860 real) |
| [v7](v7/notes.md) | `osmium_position_aware.py` | 1 | OSMIUM + position skew (stop adding when ±40, unwind at ±65) | ~9,450/day | *(pending)* |
| [v8](v8/notes.md) | `osmium_reversion.py` | 1 | OSMIUM + extreme reversion (tighter quotes when \|dev\|≥10, 74-95% revert) | ~9,450/day | 2,776 (~27,760 real) |
| [v9](v9/notes.md) | `combined_best.py` | 1 | **BEST COMBINED**: v5.2 root + v3 osmium | ~82,600/day | *(pending)* |

---
To add a new version: add folder `vN/`, put the strategy file inside with a descriptive name, and fill in `vN/notes.md`.
Run with: `python backtest.py --round ROUND1 --strategy strategies/vN/<filename>.py`
