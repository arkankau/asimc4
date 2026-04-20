# IMC Prosperity 4 — Game Info

## Round Schedule (CEST / UTC+2)

| Round | Start | Close |
|---|---|---|
| Tutorial | — | — |
| Round 1 | Tue Apr 14 12:00 | Fri Apr 17 12:00 |
| Round 2 | Fri Apr 17 12:00 | Mon Apr 20 12:00 |
| Round 3 | Fri Apr 24 12:00 | Sun Apr 26 12:00 |
| Round 4 | Sun Apr 26 12:00 | Tue Apr 28 12:00 |
| Round 5 | Tue Apr 28 12:00 | Thu Apr 30 12:00 |

Rounds 2 and 3 include a 3-hour calculation window between them where scores are inaccessible.

## Game Mechanics

- 5 rounds total, 16 simulation days
- Algorithm runs 10,000 iterations per round (1,000 during dev testing)
- No interaction between players' algorithms — you only trade against bots
- Last successfully processed submission before round end is locked in
- Manual trades are separate from algo and don't affect algo PnL

## Tutorial Round Products

| Product | Fair Value | Behavior | Position Limit |
|---|---|---|---|
| `EMERALDS` | ~10000 (flat) | Extremely stable, max ±4 deviation | 80 |
| `TOMATOES` | ~4980 | Noisy mean-reversion, range ~4946–5011 | 80 |

## Round 1 Products

| Product | Behavior | Position Limit | Strategy hint |
|---|---|---|---|
| `INTARIAN_PEPPER_ROOT` | Strong linear uptrend: ~10000→11000→12000→13000 across days -2/-1/0. Rate: ~0.1/timestamp. Described as "similar to EMERALDS" (predictable fair value) + "slow-growing root" | 80 | Trend-follow; fair value = start + 0.1*t |
| `ASH_COATED_OSMIUM` | Mean-reverts around 10000, range ~9980–10023. Described as "volatile with a hidden pattern" | 80 | Market-make around 10000; investigate hidden pattern |

### OSMIUM notes
- Bid-ask spread from bots: avg ~16.6, min 6, max 21
- Appears to oscillate around 10000 but no strong sinusoidal pattern identified yet
- "Hidden pattern" hint suggests fair value may not be simply constant — needs deeper analysis

### PEPPER_ROOT notes  
- Day -2: 9998→11001 (+1003), Day -1: 10998→11998 (+1000), Day 0: 11998→13000 (+1002)
- Intraday trend is linear: ~0.1 XIREC per timestamp (100ms step)
- Each day starts ~1000 higher than previous day's start

## Round 1 Manual Challenge

**Products**: `DRYLAND_FLAX`, `EMBER_MUSHROOM` (auction only, no continuous trading)

**Mechanics**: Submit a single limit order (price + qty). Exchange picks clearing price that maximizes volume (breaks ties with higher price). You submit last → last in queue at any price level.

**Guaranteed buyback**:
- `DRYLAND_FLAX`: 30 XIREC/unit (no fees)
- `EMBER_MUSHROOM`: 20 XIREC/unit (fee: 0.10/unit)

**Strategy**: Bid as high as possible below clearing price to maximize fill, since buyback is guaranteed profit.

## Round 2 — "Growing Your Outpost"

**Products**: Same — `ASH_COATED_OSMIUM`, `INTARIAN_PEPPER_ROOT` (position limit 80 each)

**Goal**: Hit 200,000 XIREC net PnL threshold before Phase 2 leaderboard reset.

### Market Access Fee (MAF)
- Bid for 25% more order book quotes (extra quotes fit naturally into existing distribution)
- Implement as `bid()` method in Trader class — returns an int (negative treated as 0)
- **Blind auction**: top 50% of bids accepted → pay their bid, get extra volume
- Bottom 50% pay nothing but get no extra volume
- Bid is subtracted from Round 2 profits: `profit = algo_profit - bid`
- MAF is one-time fee; ignored during testing (only compared at final round simulation)
- Testing uses 80% of quotes (slightly randomized each submission — submitting same file repeatedly has very limited payoff)
- Median computed only from teams that submitted a trader.py (no submission = bid 0, but excluded from median)

### Manual Challenge — "Invest & Expand"
Budget: **50,000 XIRECs** allocated as percentages (0–100% each, total ≤ 100%)

**PnL = Research × Scale × Speed − Budget_Used**
where `Budget_Used = (r + s + sp) / 100 * 50,000`

**Research(r)** = `200,000 * ln(1+r) / ln(101)` — logarithmic, 0→200,000
**Scale(s)** = `7 * s/100` — linear, 0→7
**Speed(sp)** = rank-based multiplier 0.1→0.9:
  - Highest investment → 0.9, lowest → 0.1, linear by rank
  - Tied investments share the same (highest tied) rank
  - Teams that don't submit are excluded from rank calculation
  - Inputs are integers (%)

### Optimal Manual Allocation math
Optimality condition (equal marginal returns on R and S):
`s = (1+r) * ln(1+r)` with constraint `r + s + sp = 100`

| Speed % | Research % | Scale % | PnL (if Sp=0.9) | PnL (if Sp=0.1) |
|---|---|---|---|---|
| 0 | 23 | 77 | ~618k | ~24k |
| 10 | 21 | 69 | ~540k | ~21k |
| 20 | 19 | 61 | ~464k | ~18k |
| 30 | 17 | 53 | ~390k | ~15k |
