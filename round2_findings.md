# Round 2 Findings

Analysis source: `ROUND_2/prices_round_2_day_{-1,0,1}.csv` and `ROUND_2/trades_round_2_day_{-1,0,1}.csv`.

## Executive summary

Round 2 preserves the same core market structure as Round 1:

- `ASH_COATED_OSMIUM` is still a tight mean-reversion / market-making product centered around roughly `10,001`.
- `INTARIAN_PEPPER_ROOT` still follows an almost deterministic upward fair-value path with bounded residual noise.
- The main Round 2 changes are quantitative rather than qualitative: pepper spreads are wider, pepper residual noise is slightly larger, and osmium trade count is higher.

## Dataset structure

- 60,000 price rows total: 3 days x 2 products x 10,000 order-book snapshots.
- 2,391 trade rows total.
- Timestamp grid still runs from `0` to `999900` in 100-unit steps inside each day.
- Counterparty tags are still unusable: `buyer` and `seller` are entirely missing.
- Only about `0.17%` of price rows have `mid_price == 0`; these are thin-book rows and should be filtered before fitting or signal work.

## Product 1: ASH_COATED_OSMIUM

Key metrics from clean rows:

- Fair value: about `10000.88`
- Mid-price sigma: about `5.10`
- Mean spread: about `16.23`
- OU AR(1) phi: about `0.739`
- OU half-life: about `2.29` ticks
- Lag-1 return autocorrelation: about `-0.50`

Interpretation:

- This is still a classic short-half-life reversion product.
- The raw reversion speed is strong, but the spread is large enough that blind aggressive mean reversion is not obviously attractive.
- The better use case is quote placement, skewing, and inventory management around a stable fair value.

Signal findings:

- L1 imbalance remains strong. At a 10-tick horizon, imbalance correlation to future mid move is about `0.63`.
- Conditioning on imbalance magnitude matters:
  - imbalance `>= 0.50`: average 10-tick markout about `+6.34`
  - imbalance `<= -0.50`: average 10-tick markout about `-6.35`
- A rolling z-score of mid around its local mean still mean-reverts:
  - z `<= -1.5`: average 10-tick markout about `+5.42`
  - z `>= +1.5`: average 10-tick markout about `-5.55`

Practical conclusion:

- Use imbalance and short-horizon deviation as skew signals, not as automatic crossing signals.
- With a half-spread around `8`, these markouts are useful for improving passive quotes and leaning inventory rather than paying the spread every time.

## Product 2: INTARIAN_PEPPER_ROOT

The dominant Round 2 edge is still the deterministic fair-value drift. A fitted linear model on clean rows gives:

`fair(day, timestamp) ~= 11999.970 + 999.985 * day + 0.001000006 * timestamp`

In practical terms, this is effectively:

`fair(day, timestamp) ~= 12000 + 1000 * day + 0.001 * timestamp`

Key metrics:

- Mean spread: about `14.12`
- Spread by day: `13.07 -> 14.12 -> 15.18`
- Residual sigma around the fitted fair value: about `2.37`
- Residual range: about `[-11.35, +11.34]`
- Residual AR(1): about `0.009`
- Residual half-life: essentially zero

Interpretation:

- The level process looks non-stationary only because the fair value itself is rising almost mechanically.
- After detrending, the residual is near-white-noise with tight bounds.
- That makes pepper a fair-value tracking problem, not a generic momentum or book-pressure problem.

Signal findings:

- Trend residual is still the cleanest signal.
- At a 10-tick horizon:
  - residual `<= -1 sigma`: average markout about `+7.56`
  - residual `>= +1 sigma`: average markout about `-5.49`
  - residual `<= -2 sigma`: average markout about `+7.92`
  - residual `>= +2 sigma`: average markout about `-5.79`
- L1 imbalance is also predictive, with about `0.65` correlation to 10-tick future mid move.

Practical conclusion:

- The cleanest pepper framework is:
  1. compute deterministic fair value from day and timestamp,
  2. maintain a structural long bias because fair value rises through the day,
  3. use negative residuals as higher-conviction buy zones,
  4. fade large positive residuals selectively, especially if inventory is already long.

## Round 1 vs Round 2 comparison

The regime did not change:

- Osmium remains stationary and mean-reverting.
- Pepper remains deterministic-trending with bounded residuals.

The main deltas:

- `ASH_COATED_OSMIUM`
  - fair value shifted slightly upward from about `10000.20` to about `10000.88`
  - half-life shortened from about `2.49` ticks to about `2.29` ticks
  - spread stayed basically unchanged around `16.2`
  - trades/day increased from roughly `420` to roughly `465`
- `INTARIAN_PEPPER_ROOT`
  - time slope stayed effectively identical at `~0.001`
  - residual sigma rose from about `2.20` to about `2.37`
  - spread widened by roughly `1` tick across the whole round profile
  - trade count stayed flat around `332` per day

## Strategy implications

- `ASH_COATED_OSMIUM`
  - build around passive market making
  - anchor fair value near `10,001`
  - skew quote placement with imbalance and short-horizon z-score
  - avoid overpaying spread for small raw markouts
- `INTARIAN_PEPPER_ROOT`
  - treat the deterministic fair-value formula as the primary state variable
  - keep a long inventory bias whenever risk limits allow
  - buy negative residuals aggressively relative to positive residuals
  - be aware that widening spread reduces the attractiveness of short holding-period aggression

## Cautions

- All markouts above are raw future mid moves, not realized PnL.
- Counterparty tags are unavailable, so there is no reliable informed-flow segmentation.
- Pepper still trends strongly, but the per-10-tick drift is only about `+1`, which is much smaller than the spread. Pure aggression needs either longer holding periods or residual dislocation on top of the base trend.
