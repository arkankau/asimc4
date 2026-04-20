# Round 1 EDA — Data Trends

Analysis of `ROUND1/prices_round_1_day_{-2,-1,0}.csv` and `ROUND1/trades_round_1_day_{-2,-1,0}.csv`.

## Dataset shape

- 2 products: `ASH_COATED_OSMIUM`, `INTARIAN_PEPPER_ROOT`.
- 3 days per product (-2, -1, 0), 10 000 price snapshots per (day, product) = **60 000 total order-book rows**.
- Timestamp grid: 0 → 999 900 in steps of 100 per day (approx. every tick).
- Prices schema: L3 book (bid/ask price & volume at 3 levels) + `mid_price` + `profit_and_loss` (always 0 in historical data).
- Trades schema: market trades — 2 276 rows total across 3 days, ~400/day per product. `buyer` and `seller` are **100% NaN** (no counterparty tags in this dataset).
- 103 rows (0.17%) have `mid_price == 0` with both top-of-book sides NaN — treat as **thin-book / discard** ticks.

## Product 1 — `ASH_COATED_OSMIUM`: mean-reverting around 10 000

| Metric | Value |
|---|---|
| Per-day mean mid | 9 980 / 9 984 / 9 988 (d-2 / d-1 / d0) |
| Linear slope | +1.5 / day ≈ **flat** |
| AR(1) on mid (phi) | **0.757** |
| OU half-life | **≈ 2.5 ticks** |
| Long-run mean (mu) | **10 000.2** |
| Residual sigma | 5.35 |
| Day-to-day drift | −16.5, −1.0, −6.0 (bounded, no trend) |
| Tick-to-tick log-return autocorr (lag 1) | **−0.495** (bid-ask bounce) |
| 50-tick z-score zero-crossings | 29% of ticks |

**Takeaway:** classic OU / bid-ask-bounce regime. Price oscillates tightly around **10 000** with an extremely short half-life. Prime candidate for **mean-reversion market-making** with fair value = 10 000 (or short rolling mean) and inventory skew.

### Spread and book

| | |
|---|---|
| Mean spread | **16.2**, median 16, stable across all 3 days |
| Spread range | 5–22, clustered at 9–11 and at 16 (bimodal: aggressive vs. passive book states) |
| Best-bid changes | 53.8% of ticks |
| L2 distance from L1 | ≈ 3 ticks (present 98% of ticks) |
| L3 distance from L1 | ≈ 9–10 ticks (present only 2.6% of ticks) |
| Top-level imbalance | mean ~0, std 0.23 (weak directional signal) |
| Micro-price − mid | mean ~0, std 1.78 (micro-price barely deviates from mid) |

### Market trades

| | |
|---|---|
| Count/day | ~420 |
| Avg size | 5.2 (max 10) |
| Price vs mid (mean, std) | +0.14, 8.08 (symmetric, wide) |
| Aggressor buy : sell | 647 : 618 (balanced, no order-flow bias) |

## Product 2 — `INTARIAN_PEPPER_ROOT`: deterministic linear drift +1000/day

**This is the dominant, actionable signal of Round 1.**

| Metric | Value |
|---|---|
| Per-day mean mid | 10 483 / 11 480 / 12 474 (d-2 / d-1 / d0) |
| Per-day drift (last − first) | **+1 003, +999.5, +1 001.5** (≈ +1 000/day, consistently) |
| Linear fit | `fair(t) = 12 000 + 0.001 · t_global` where `t_global = day · 1 000 000 + timestamp` |
| Slope per tick | +0.001 (1 unit per 1 000 timestamps) |
| Slope per day | +1 000.005 |
| Residual sigma | **2.20** |
| Residual min / max | **−10.70 / +10.60** (bounded) |
| Residual AR(1) (phi) | **0.0084** (no autocorr — white noise around the line) |
| Residual half-life | ~0 (fully detrended signal is memoryless) |
| Mid-price level autocorr lag 1000 | ~1.00 (unit-root visually, but fully explained by linear drift) |
| Tick-to-tick log-return autocorr (lag 1) | −0.500 (bid-ask bounce around trend) |

**Takeaway:** mid_price oscillates as **white noise with std ~2.2 around a perfectly linear trend of +0.001 per timestamp**. The residual is essentially i.i.d. and bounded to ±11. This means at any point in time you know the fair value **deterministically**: buy whenever `mid < fair − k`, sell whenever `mid > fair + k`.

### Spread and book

| | |
|---|---|
| Mean spread | 12.0 (d-2) → 13.0 (d-1) → 14.1 (d0) — **widens day-by-day** |
| Spread mode | 11 (very peaked: 3 069 ticks) + secondary mode around 2–3 |
| Best-bid changes | 42.9% of ticks (calmer than ASH) |
| L2 distance from L1 | ≈ 3 ticks (present 97% of ticks) |
| L3 distance from L1 | ≈ 11–12 ticks (present 2.3%) |
| Top-level imbalance | mean ~0, std 0.19 (weaker than ASH) |
| Micro-price − mid | mean ~0, std 1.38 |

### Market trades

| | |
|---|---|
| Count/day | ~340 |
| Avg size | 5.2 (max 8) |
| Price vs mid (mean, std) | −0.38, 5.51 |
| Aggressor buy : sell | 492 : 518 (balanced) |

**Note:** spread widening across days is **not** a % effect — it's additive. This may hurt market-making round-trip PnL over time.

## Cross-product observations

- **Same tick size = 1, same order-book structure, same L2/L3 geometry** (≈ 3 and ≈ 10 ticks behind best).
- **Volatility is flat intraday**: per-tick return std is constant across the 10 time buckets of each day for both products. No open/close effect.
- **Book is 98% populated at L1/L2, ~2-3% at L3.** L3 can be ignored for fair-value estimation.
- **Order-flow imbalance and micro-price deviation are both very weak** — top-level book doesn't predict short-term direction.
- **No counterparty info** in trades; no way to identify informed flow.

## Strategy seeds (for deep-research)

1. **INTARIAN_PEPPER_ROOT — deterministic drift**
   - Known `fair(t) = 12 000 + 0.001 · t_global`. Residual is white noise with std 2.2 and hard cap ±11.
   - **Entry rule:** buy when mid < fair − k · σ (e.g. k = 1.5 → threshold ~3.3 from fair); sell symmetrically.
   - Strong directional edge exists in addition: always buy/hold bias → buy-and-hold yields +3 000 per unit over the 3 days. Position limit / inventory management matter.
   - Watch: spread widens over time — execution quality deteriorates.

2. **ASH_COATED_OSMIUM — OU / market-making**
   - Fair value = 10 000 (stable long-run mean, half-life 2.5 ticks).
   - **Market-maker:** quote around 10 000 ± (spread/2), lean bid/ask size with inventory skew.
   - Mean-reversion half-life is ~2–3 ticks, so positions unwind fast naturally.
   - Tick-to-tick lag-1 return autocorr = −0.5 → bid-ask-bounce-harvesting MM profits are expected.

3. **Meta-signals that appear absent:**
   - Order-flow imbalance is too noisy to be a primary signal.
   - No time-of-day regime, no counterparty information, no obvious trade clustering.
   - L3 depth is too sparse to be useful.

## Open questions / things to verify before trusting

- Is the INTARIAN linear drift a **feature of the historical sample** only, or is it expected to continue in the round? Check problem statement for any story/fundamental justification (e.g., "price rises 1 000 per day").
- Position limits for each product (not in data — need the round spec).
- Do we get counterparty tags in live round? If yes, informed-flow signals may emerge.
- The ±11 cap on INTARIAN residuals may be exploitable directly (mean-reversion when |residual| > 8).
