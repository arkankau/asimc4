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

Round 2 market access approximation:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log \
  --maf-contract won \
  --maf-data-mode observed-is-baseline
```

Or resolve the contract automatically from `Trader.bid()` against a local cutoff:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log \
  --maf-contract auto \
  --maf-threshold 15
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

## Round 2 Market Access Fee

If the strategy defines `Trader.bid()`, the replay runner can approximate the round-2 Market Access Fee flow:

- winning the contract pays the returned MAF once and unlocks the extra quote share
- losing the contract pays nothing and stays on the baseline share
- `--maf-contract won|lost` forces the outcome
- `--maf-contract auto --maf-threshold X` treats `Trader.bid() >= X` as a local proxy for winning

Because offline logs only contain one observed market view, the runner makes the quote expansion explicit:

- `--maf-data-mode observed-is-baseline`: assume the log already reflects only the baseline allocation; winners get an approximate volume upscale
- `--maf-data-mode observed-is-full`: assume the log reflects the full market; losers get an approximate downscale to baseline

Defaults:

- baseline share: `0.75`
- extra share: `0.25`

This is intentionally approximate. The runner scales observed book and tape volume, but it cannot reconstruct the true missing quote set from historical data.
