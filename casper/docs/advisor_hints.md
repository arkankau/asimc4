# Advisor Hints (Synthia)

## 1. Spotting Trends
> "Take Intarian Pepper Root. Slow growth. Predictable supply. Subtle shifts. Up. Down. Repeating moods."
> "When the spread stops behaving like noise and starts behaving like intention — that's usually when something is forming."

**Interpretation**: IPR has a slow, predictable uptrend. The hint about "repeating moods" and spread behavior suggests watching when the spread widens/narrows beyond its normal noise — this is a signal. Could apply to both products.

---

## 2. Strategic Orders
> "Keep fair value in the back of your head. Does my order feel intentional and calm, or rushed?"
> "Nudge the size. Adjust the price. When it stops feeling awkward and starts feeling right, you're close."

**Interpretation**: Don't post aggressive/oversized orders. Stay close to fair value, post inside the spread at reasonable sizes. Markets penalize you for looking desperate. Position-aware sizing — scale down when inventory is extreme.

---

## 3. Auction Dynamics
> "Your final order actually matters — it affects the auction clearing price itself."
> "You could nudge the outcome instead of just participating."

**Interpretation**: There may be an end-of-period auction where the clearing price is determined by aggregated orders. Your last order can shift the clearing price. Simulate where orders bunch up and position yourself there.

---

## 4. Tipping the Scale
> "Volume is the last thing that still has weight. You don't need a lot."
> "Just looking for the point where volume almost tips. Where the market is already leaning and one small addition changes where everything settles."
> "Add volume there and watch how fast things settle."

**Interpretation (confirmed by data)**: ASH_COATED_OSMIUM reverts to 10000 with extreme reliability at price extremes:
- At ±5 deviation: 55% chance of reversion next tick, avg return -2.0/+1.9
- At ±10 deviation: **74.9% chance**, avg return -4.3/+4.7
- At ±15 deviation: **95% chance**, avg return -7.1/+7.6

When price is at an extreme, adding volume on the contra side = "tipping the scale." The market is already leaning back, you just provide the final nudge.
