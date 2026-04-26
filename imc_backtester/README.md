# Options Backtester

This repo now has an explicit options-first package: `options_backtester`.

Use it for Round 3 VEV voucher research. The older `imc_backtester` package remains in place for legacy log replay and compatibility entrypoints.

## Primary Workflow

Replay the dedicated VEV options universe with persistent quotes, smile-based valuation diagnostics, and explicit liquidation assumptions:

```bash
python3 -m options_backtester /path/to/trading.py /path/to/3/ROUND_3
```

Useful options:

```bash
python3 -m options_backtester /path/to/trading.py /path/to/3/ROUND_3 \
  --day 0 \
  --execution-mode conservative \
  --inventory-mark-mode conservative \
  --liquidation-mark-mode haircut_close \
  --bootstrap-repetitions 0
```

The legacy alias still works:

```bash
python3 -m imc_backtester options /path/to/trading.py /path/to/3/ROUND_3
```

## Legacy IMC Runner

Small local replay runner for current IMC Prosperity downloaded `.log` files.

It uses the same broad structure as `jmerle/imc-prosperity-3-backtester`:

- parse per-timestamp book snapshots
- build a `TradingState`
- call `Trader.run`
- enforce position limits
- match against visible depth first, then the trade tape
- emit IMC-style `activitiesLog`, `graphLog`, `tradeHistory`, and per-timestamp logs

## Usage

Run the generic legacy log replay from the repo root:

```bash
python3 -m imc_backtester /path/to/trading.py /path/to/submission.log
```

Replay Round 3 raw CSVs with option-aware marking:

```bash
python3 -m imc_backtester round3csv /path/to/trading.py /path/to/3/ROUND_3 \
  --mark-mode smile \
  --timestamp-mode local
```

Replay the dedicated VEV options universe with end-of-round settlement:

```bash
python3 -m imc_backtester options /path/to/trading.py /path/to/3/ROUND_3
```

By default, `round3csv` treats `day_0`, `day_1`, and `day_2` as separate rounds:

- inventory and `traderData` reset each day
- end-of-day PnL is marked and then the next day starts flat

Use `--day-mode continuous` only if you explicitly want the old carry-through behavior.

Restrict to one historical day:

```bash
python3 -m imc_backtester round3csv /path/to/trading.py /path/to/3/ROUND_3 \
  --day 0 \
  --bootstrap-repetitions 0
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

## Round 3 CSV Backtester

The `round3csv` mode is for the raw `prices_round_3_day_*.csv` and
`trades_round_3_day_*.csv` files instead of downloaded IMC `.log` JSON.

It supports:

- direct replay from the raw Round 3 folder
- option-aware marking for vouchers via `--mark-mode smile`
- alternative voucher marks via `--mark-mode mid|conservative|intrinsic`
- `--timestamp-mode local|global` to control what the strategy sees in `state.timestamp`
- `ROUND3_DAY`, `ROUND3_LOCAL_TIMESTAMP`, `ROUND3_GLOBAL_TIMESTAMP`, and `ROUND3_TTE_MILLIDAYS` in `state.observations.plainValueObservations`
- `--day-mode split|continuous` to choose between round-like daily resets and one continuous multi-day replay

Timestamp/day-mode notes:

- In `--day-mode split`, the runner now coerces `--timestamp-mode global` to `local`, because each historical day is replayed as a separate round and many strategies use `state.timestamp` for within-day logic.
- In `--day-mode continuous`, `--timestamp-mode local` is allowed, but the runner will warn because timestamps reset each day while inventory carries through.
- The CLI now prints per-day summaries so multi-day replays are easier to sanity-check.

Important caveat:

- this is still an approximation; it does not know the exchange's hidden end-of-round liquidation fair value

## VEV Options Backtester

`options_backtester` is now the primary Round 3 runner.
It narrows the replay universe to:

- `VELVETFRUIT_EXTRACT`
- all `VEV_*` vouchers

and drops unrelated Round 3 symbols such as `HYDROGEL_PACK`.

It keeps the same `Trader.run` interface, but changes the defaults to be more
options-research-friendly:

- `--day-mode split` by default, so historical day files are replayed as separate rounds
- `--timestamp-mode local` by default, so `state.timestamp` behaves like an IMC round clock
- persistent passive quotes rest until canceled, repriced, filled, or day-end flushed
- fair value is computed from a smile-consistent cross-strike view of the vouchers
- running inventory marks and day-end liquidation marks are explicit choices instead of one blended mark

Example:

```bash
python3 -m options_backtester vev_trader_stage1.py 3/ROUND_3 \
  --day 0 \
  --execution-mode conservative \
  --bootstrap-repetitions 0
```

Notes:

- `options` is an options-first approximation of the round, not a perfect exchange simulator
- the end-of-round settlement price is still a model proxy, because the real IMC hidden liquidation fair value is not observable from the CSVs
- `python3 -m imc_backtester options ...` and `python3 -m imc_backtester round3 ...` remain compatibility aliases

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

## Calibration Mode

Compare replay assumptions against an official IMC result JSON:

```bash
python3 -m imc_backtester calibrate /path/to/trading.py /path/to/submission.log /path/to/official.json
```

Restrict the grid or pass explicit limits:

```bash
python3 -m imc_backtester calibrate /path/to/trading.py /path/to/submission.log /path/to/official.json \
  --match-trades all \
  --submission-trades sanitize \
  --limit VEV_5200=300
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
