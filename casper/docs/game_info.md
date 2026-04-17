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
