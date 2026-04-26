# VEV Round 3 Multi-Trader Design

## Goal

Build three separate, directly submittable Round 3 VEV trader files, each implementing a different options trading style, then select the strongest live bot for `vev_trader.py`.

The three target strategies are:

1. `vev_trader_zscore.py`: treat each voucher as its own time series and trade simple mean reversion.
2. `vev_trader_bs.py`: use Black-Scholes with a single shared volatility estimate to price vouchers independently.
3. `vev_trader_smile.py`: fit a cross-strike implied-volatility smile and trade residual mispricings.

Each file must be standalone and directly submittable on its own. No local-repo imports are allowed in the generated submission files; only standard-library imports and IMC `datamodel` imports are permitted.

## Context

This repository already contains a strong Round 3 options framework in `vev_trader_core.py`, generated variants in `build_vev_variants.py`, a dedicated Round 3 options backtester in `imc_backtester/options_runner.py`, and an exploratory notebook in `round3_eda.ipynb`.

Round 3 data findings that drive this design:

- `VEV_5200`, `VEV_5300`, and `VEV_5400` are the best core trading strikes.
- `VEV_5100` and `VEV_5500` are plausible secondary expansion strikes.
- `VEV_6000` and `VEV_6500` are effectively dead and should not drive signal generation.
- `VEV_4000` and `VEV_4500` are relatively wide and noisy, so they should not drive the main live strategy.
- `VELVETFRUIT_EXTRACT` mean reversion exists but appears weaker than the voucher-relative residual signal.
- The current notebook and stronger public Prosperity Round 3 writeups both point toward smile-based residual trading as the most promising live approach.

## Approaches Considered

### Approach A: Fully independent handwritten trader files

Each strategy would own its own option math, signal generation, sizing, and execution code.

Pros:

- Maximum freedom per file.
- Easy to think about each trader in isolation.

Cons:

- Large duplication.
- Higher risk of inconsistent risk controls and execution behavior.
- Harder to compare strategies fairly.

### Approach B: Shared internal source plus generated standalone trader files

Maintain shared internal logic inside the repo, then generate self-contained submittable outputs for each trader file.

Pros:

- Best fit with the current `vev_trader_core.py` and `build_vev_variants.py` pattern.
- Allows fairer comparison by keeping common execution and risk controls aligned.
- Keeps each final file directly submittable.

Cons:

- Requires some generation plumbing.
- Internal architecture is slightly more abstract.

### Approach C: One production trader plus lighter research probes

Build only one full live bot and keep the other two as partial research variants.

Pros:

- Fastest path to one candidate submission.

Cons:

- Weak comparison.
- Harder to learn which signal family is actually strongest.

## Chosen Direction

Use Approach B.

Internally, keep shared logic where it reduces duplication and preserves consistent execution. Externally, emit three fully standalone trader files plus one convenience default file:

- `vev_trader_zscore.py`
- `vev_trader_bs.py`
- `vev_trader_smile.py`
- `vev_trader.py`

`vev_trader.py` will mirror the current best live candidate after comparative testing.

## Output Files

### `vev_trader_zscore.py`

Standalone trader implementing simple voucher-by-voucher time-series mean reversion.

Intent:

- Reproduce the simplest public-style Round 3 implementation pattern.
- Provide a baseline that does not depend on explicit options theory.

### `vev_trader_bs.py`

Standalone trader implementing Black-Scholes pricing with a single shared live volatility estimate.

Intent:

- Represent the classic options-aware but still simple approach.
- Price each traded voucher independently once spot, strike, expiry, and volatility are known.

### `vev_trader_smile.py`

Standalone trader implementing cross-strike smile fitting and residual scalping.

Intent:

- Represent the strongest theory-backed approach for these data.
- Use all liquid strikes together to define fair relative pricing.

### `vev_trader.py`

Standalone trader identical to the currently preferred live bot after testing.

Intent:

- Provide one canonical submission file without forcing the user to remember which candidate won.

## Common Trading Scope

All three traders should share the same broad trading universe constraints so comparisons remain meaningful.

### Core traded strikes

- `VEV_5200`
- `VEV_5300`
- `VEV_5400`

### Secondary expansion strikes

- `VEV_5100`
- `VEV_5500`

These should trade with smaller size or only under stronger conditions.

### Excluded from signal generation

- `VEV_6000`
- `VEV_6500`

These may still appear in the file as known products for completeness, but they should not drive live signals.

### Not primary alpha drivers

- `VEV_4000`
- `VEV_4500`
- `VELVETFRUIT_EXTRACT`

The underlying is required for option valuation, but version 1 should not add a separate spot alpha strategy unless testing later shows it is clearly additive.

## Strategy Definitions

### 1. Z-Score Trader

#### Idea

Treat each voucher as its own mean-reverting time series.

#### Signal logic

- Maintain recent mid-price history per traded voucher.
- Estimate rolling mean and dispersion.
- Buy when price is sufficiently below its recent reference.
- Sell when price is sufficiently above its recent reference.

#### Characteristics

- Ignores cross-strike structure.
- Easiest to explain and debug.
- Serves as the “simple market-behavior” baseline.

### 2. Black-Scholes Trader

#### Idea

Price each traded voucher using Black-Scholes and one shared volatility estimate.

#### Signal logic

- Read spot from `VELVETFRUIT_EXTRACT`.
- Use strike-specific expiry and time-to-expiry logic.
- Estimate a single live volatility number from the liquid middle strikes.
- Compute fair price for each traded voucher.
- Trade the difference between market mid and model fair value.

#### Characteristics

- Uses options theory but still prices each traded voucher mostly independently.
- More interpretable than the smile model.
- Good fallback if smile fitting proves unstable.

### 3. Smile Trader

#### Idea

Use all liquid strikes together to fit a fair implied-volatility curve, then trade the options that deviate from that curve.

#### Signal logic

- Invert implied vol for liquid smile strikes.
- Fit a smooth curve across moneyness.
- Convert fitted vol back into fair price.
- Trade residual mispricing in price space.
- Optionally use adjacent-strike and vertical-spread sidecars if they add value without destabilizing the core.

#### Characteristics

- Best aligned with current notebook findings.
- Best aligned with the strongest public Round 3 writeups.
- Expected to be the strongest live candidate before testing.

## Execution Model

All three traders should follow the same high-level execution loop to keep comparisons fair.

1. Read `VELVETFRUIT_EXTRACT` and compute spot mid.
2. Read the selected voucher books.
3. Compute strategy-specific fair value or signal.
4. Convert signal into target positions per voucher.
5. Rebalance toward those targets using a shared execution style.

The execution style should preserve the current repo’s practical strengths:

- cross only when edge is strong
- otherwise quote passively near fair value
- use smaller size on secondary strikes
- de-risk late in the session
- flatten near the end of the round

## Risk and Positioning

Comparisons should differ mainly in signal quality, not in risk appetite.

Common rules:

- Core strikes get the largest sizing.
- Expansion strikes get smaller sizing.
- Dead or noisy strikes do not drive strategy decisions.
- Late-session size should be reduced.
- Final flattening should remain enabled.
- Position limits must remain exchange-safe and voucher-aware.

If the current code already contains proven execution and flatten logic, it should be preserved unless there is a clear strategy-specific reason to change it.

## Testing and Selection

The goal is not just to create three files. The goal is to select the strongest live bot.

### Comparison process

Each standalone trader should be replayed on:

- each historical Round 3 day separately
- combined split-day replay across all available Round 3 days

### Comparison metrics

- total profit
- day-by-day consistency
- drawdown behavior
- concentration by strike
- whether profits are coming from the intended liquid core or from noisy edge cases

### Winner rule

Default promotion order:

1. Prefer `vev_trader_smile.py` if it is clearly best or tied-best on profit without being the worst on consistency.
2. Use `vev_trader_bs.py` as fallback if the smile trader is unstable or too parameter-sensitive.
3. Keep `vev_trader_zscore.py` as the baseline sanity check rather than the expected final winner.

After selection, `vev_trader.py` should mirror the best live bot exactly.

## Implementation Notes

- Preserve the current generated-output workflow if it still helps produce self-contained files.
- Generated trader files must remain readable enough for manual submission if needed.
- Avoid local helper imports in the final output files.
- Reuse existing option math and rebalancing logic where it is already solid.
- Keep each submission file self-contained and valid on its own.

## Non-Goals

- Do not build one hybrid trader that mixes all three signal families immediately.
- Do not add a separate standalone `VELVETFRUIT_EXTRACT` directional strategy in version 1.
- Do not optimize deep OTM or deep ITM edge cases before the liquid middle strikes are working.
- Do not rely on one lucky replay to choose the live winner.

## Expected Outcome

At the end of this implementation, the repository should contain:

- three standalone, directly submittable VEV Round 3 trader files
- a clear testing workflow to compare them on the repo’s Round 3 data
- one promoted live default in `vev_trader.py`

The expected favorite going into implementation is the smile-based trader, with the Black-Scholes trader as the most credible fallback and the z-score trader as the simplest baseline.
