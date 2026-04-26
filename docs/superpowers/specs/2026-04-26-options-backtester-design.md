# Options-First Backtester Design

**Goal**

Turn the repo's Round 3 options replay into an explicit `options_backtester` package that is built for smile-based options research, conservative execution replay, and risk-aware PnL analysis instead of generic IMC log replay.

**Context**

The current repo already contains useful pieces:

- raw Round 3 CSV loading in `imc_backtester/round3_csv_runner.py`
- an options-only CLI in `imc_backtester/options_runner.py`
- Black-Scholes and smile-mark helpers inside `imc_backtester/round3_csv_runner.py`
- a one-shot order matcher in `imc_backtester/runner.py`

Those pieces are useful, but they still mix three concerns that should be separated for options research:

1. signal quality
2. execution quality
3. marking / liquidation quality

Round 3 EDA in `round3_eda.ipynb` points to smile residuals, adjacent-strike IV spreads, and vertical-spread consistency as the main alpha sources. The backtester should therefore be centered on fair-value estimation across strikes, with execution replay as a second layer.

## Design Summary

The refactor introduces a new `options_backtester` package with four explicit layers:

1. `market replay`
2. `fair value`
3. `execution`
4. `risk and reporting`

Legacy `imc_backtester` options entrypoints stay as compatibility shims that call the new package.

## Architecture

### 1. Market Replay Layer

Responsibilities:

- load and filter the Round 3 options universe
- expose per-timestamp snapshots and tape trades
- keep IMC-compatible `TradingState` construction
- preserve day-mode and timestamp-mode controls

This layer should continue to rely on the existing raw CSV loader logic, but the options package should wrap it in an options-first API.

### 2. Fair-Value Layer

Responsibilities:

- compute smile-consistent fair prices for vouchers
- invert implied vol from available market prices
- fit a cross-strike smile using trusted anchors
- expose greeks and residual diagnostics
- enforce or at least flag no-arbitrage conditions

Rules:

- prioritize liquid near-ATM strikes as fit anchors
- price deep ITM / deep OTM names from the fitted smile unless they are clearly liquid
- expose three mark families:
  - `signal_fair`
  - `inventory_mark`
  - `liquidation_mark`

### 3. Execution Layer

Responsibilities:

- keep passive orders resting across ticks
- support immediate aggressive fills against visible top-of-book
- support conservative passive fills using touch / trade-through / queue depletion assumptions
- expose fill reasons and queue assumptions

Rules:

- same-tick aggressive fills are allowed
- same-tick passive fills are not allowed by default
- passive orders stay live until canceled, repriced, filled, or end-of-day flushed
- execution assumptions are grouped into named presets such as `conservative`, `balanced`, and `optimistic`

### 4. Risk and Reporting Layer

Responsibilities:

- compute realized and marked PnL
- track delta / vega / gamma / theta exposures
- surface per-strike inventory and concentration
- report liquidation under explicit proxy assumptions

PnL should be decomposed rather than reported as a single opaque number.

## Package Layout

The target package layout is:

- `options_backtester/__init__.py`
- `options_backtester/__main__.py`
- `options_backtester/market.py`
- `options_backtester/fair_value.py`
- `options_backtester/execution.py`
- `options_backtester/runner.py`

Compatibility path:

- `imc_backtester` remains in place for legacy imports
- `imc_backtester` options entrypoints delegate to `options_backtester`

## Output Shape

The options runner output should include:

- existing replay artifacts:
  - `activitiesLog`
  - `graphLog`
  - `tradeHistory`
  - `logs`
  - `positions`
- new options-focused metadata:
  - execution mode
  - inventory mark mode
  - liquidation mark mode
  - fill reasons
  - valuation diagnostics
  - exposure path summaries

## Incremental Implementation

The refactor should happen in four passes:

1. extract fair-value logic and diagnostics into a dedicated module
2. replace one-shot options matching with persistent working orders
3. report decomposed PnL and explicit liquidation assumptions
4. promote `options_backtester` to the primary package and keep legacy options shims

## Non-Goals

The refactor does not try to solve:

- exact replication of hidden IMC liquidation values
- exact venue queue reconstruction
- a perfect all-rounds generic IMC simulator

The purpose is a stronger options research simulator, not exact website-score reproduction.
