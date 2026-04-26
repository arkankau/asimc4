# Options Backtesting Guide

This repo's primary Round 3 options workflow is the `options_backtester` package.

Use it for:

- VEV voucher replay on `3/ROUND_3`
- smile-based fair-value diagnostics
- persistent passive-order replay
- explicit inventory and liquidation marks

## Primary Command

Run from the repo root:

```bash
python3 -m options_backtester <trader-file.py> 3/ROUND_3
```

Example:

```bash
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 \
  --day 0 \
  --execution-mode conservative \
  --inventory-mark-mode conservative \
  --liquidation-mark-mode haircut_close \
  --bootstrap-repetitions 0
```

## Compatibility Alias

The old entrypoint still works and calls the new runner:

```bash
python3 -m imc_backtester options <trader-file.py> 3/ROUND_3
```

## Important Flags

- `--day 0`
  Restrict replay to one historical day. Repeat for multiple days.

- `--day-mode split|continuous`
  `split` resets inventory per historical day. `continuous` carries state across days.

- `--timestamp-mode local|global`
  Controls what `state.timestamp` the strategy sees.

- `--execution-mode conservative|balanced|optimistic`
  Controls passive-fill assumptions and queue haircuts.

- `--inventory-mark-mode signal|conservative`
  Chooses how running inventory PnL is marked.

- `--liquidation-mark-mode signal|haircut_close`
  Chooses the end-of-day settlement proxy.

- `--bootstrap-repetitions 0`
  Disables Monte Carlo metrics for faster iteration.

## Output

By default the runner writes:

```text
<trader-stem>.options.backtest.json
```

Example:

```text
vev_trader_simple.options.backtest.json
```

The output includes:

- `activitiesLog`
- `graphLog`
- `tradeHistory`
- `logs`
- `positions`
- `metrics`
- `backtestMetadata`

Each `logs` entry now also includes:

- `fillEvents`
- `valuation`
- `restingOrders`
- `perProductPnl`

## How To Read Results

Check `backtestMetadata` first:

- `execution_mode`
- `inventory_mark_mode`
- `liquidation_mark_mode`
- `day_mode`
- `effective_timestamp_mode`

Then inspect `logs[*].valuation.diagnostics` for:

- `used_in_fit`
- `fitted_iv`
- `delta`
- `vega`
- `theta`
- `price_residual`
- `repair_flags`

If a strategy looks too good, inspect `fillEvents` and see whether PnL depends on:

- aggressive fills
- touch-and-consume passive fills
- book-cross passive fills
- generous liquidation assumptions

## Recommended Research Loop

1. Start with one day and no bootstrap:

```bash
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 --day 0 --bootstrap-repetitions 0
```

2. Compare execution assumptions:

```bash
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 --day 0 --execution-mode conservative
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 --day 0 --execution-mode balanced
```

3. Compare liquidation assumptions:

```bash
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 --day 0 --liquidation-mark-mode signal
python3 -m options_backtester vev_trader_simple.py 3/ROUND_3 --day 0 --liquidation-mark-mode haircut_close
```

4. Only trust ideas that survive conservative execution and conservative close assumptions.

## Strategy Notes For This Repo

The Round 3 EDA suggests the strongest options signals are:

- smile price residuals
- adjacent-strike IV spread dislocations
- vertical-spread arbitrage

So treat this runner as an options fair-value simulator with execution replay, not as a pure spread-capture market-making simulator.

## Verification Commands

Fast unit verification:

```bash
python3 -m unittest tests.test_options_fair_value tests.test_options_execution -v
```

Repo test discovery:

```bash
python3 -m unittest discover -s tests -v
```
