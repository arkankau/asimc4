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

---

## Round 2 — Market Access Fee (MAF) Bidding

### 5. Opportunity Valuation
> "Does the access still make sense once the fee is in the picture? Does it change how you price things? Does it shift where you want to position yourself?"

**Interpretation**: Before bidding, calculate your exact expected value from the extra volume. 25% more order book depth → ~25% more ACO fills → estimate in XIRECs. If your bid exceeds that value, it's a net loss. The access isn't inherently valuable — only if it pays back more than it costs.

---

### 6. Competing With Others (Game Theory)
> "To get full market access you need to outbid the median. Not the top. The median."
> "Every bid out there is basically someone's guess about what everyone else is going to do."

**Interpretation**: This is a Keynesian beauty contest. You need to be above the 50th percentile bid — not the highest. The optimal bid is just above your estimate of the median. Overbidding costs XIRECs. Underbidding costs market access entirely. Read whether the field is conservative or aggressive.

---

### 7. Risk Appetite
> "The more interesting move is figuring out how low you can go while still landing above the median."
> "Every XIREC you don't spend on access is a XIREC that actually does something useful."

**Interpretation**: Bid efficiency matters. Don't add a huge safety buffer — that's overpaying. But don't bid at the exact estimated median either (too risky). Find your confidence interval and bid just enough above median to be comfortable. The cost of missing the threshold is losing all extra volume.

---

### 8. Cooperation and Trust
> "The calm isn't coming from the market. It's coming from the alignment."
> "Don't rely on others continuing to act the way you expect. That's not a position. That's just hope with extra steps."

**Interpretation**: If all teams value access similarly, median bids converge and stabilize. But this is fragile — one team changing strategy shifts the median. Don't anchor your bid on assumed stable behavior from others. Budget a margin for unpredictable bids.

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
