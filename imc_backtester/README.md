# IMC Log Backtester

Small local replay runner for the current IMC Prosperity downloaded `.log` files.

It uses the same broad structure as `jmerle/imc-prosperity-3-backtester`:

- parse per-timestamp book snapshots
- build a `TradingState`
- call `Trader.run`
- enforce position limits
- match against visible depth first, then the trade tape
- emit IMC-style `activitiesLog`, `graphLog`, `tradeHistory`, and per-timestamp logs

## Usage

Run from the repo root:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log
```

Write to a custom output file:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log --out /tmp/result.json
```

Override limits:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log \
  --limit ASH_COATED_OSMIUM=80 \
  --limit INTARIAN_PEPPER_ROOT=80
```

The replay output now includes a `metrics` block with:

- exact PnL path derived from `activitiesLog`
- Sharpe-like and Sortino-like ratios
- max drawdown and profit-to-drawdown
- product concentration
- Monte Carlo block bootstrap summaries

## Metrics Mode

Analyze one result file:

```bash
python3 -m imc_backtester metrics ROUND1/logs/1/237768.json
```

Analyze a whole folder recursively:

```bash
python3 -m imc_backtester metrics ROUND1/logs --csv-out /tmp/round1_metrics.csv
```

Control Monte Carlo:

```bash
python3 -m imc_backtester metrics ROUND1/logs \
  --bootstrap-repetitions 2000 \
  --bootstrap-block-size 10
```

## Important Caveat

The downloaded IMC `tradeHistory` already contains trades involving your original `SUBMISSION`.
That means this replay is still an approximation when you use one submission's log to test a different algorithm.

The default `--submission-trades sanitize` mode treats those rows as one-sided external liquidity, which is usually the safest option.

Other modes:

- `sanitize`: keep the trade, but only the non-submission side is usable as external tape
- `full`: treat submission trades like normal market trades
- `exclude`: drop submission trades entirely

For a truly clean offline backtester, the best input would be logs from a passive or no-order submission.
