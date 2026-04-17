"""Deep analysis of ASH_COATED_OSMIUM to find hidden pattern."""
import csv
import math
from collections import defaultdict

def load_prices(day):
    rows = []
    with open(f"prices_round_1_day_{day}.csv") as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row['product'] == 'ASH_COATED_OSMIUM':
                ts = int(row['timestamp'])
                bp1 = float(row['bid_price_1']) if row['bid_price_1'] else None
                bv1 = int(row['bid_volume_1']) if row['bid_volume_1'] else 0
                bp2 = float(row['bid_price_2']) if row['bid_price_2'] else None
                bv2 = int(row['bid_volume_2']) if row['bid_volume_2'] else 0
                bp3 = float(row['bid_price_3']) if row['bid_price_3'] else None
                bv3 = int(row['bid_volume_3']) if row['bid_volume_3'] else 0
                ap1 = float(row['ask_price_1']) if row['ask_price_1'] else None
                av1 = int(row['ask_volume_1']) if row['ask_volume_1'] else 0
                ap2 = float(row['ask_price_2']) if row['ask_price_2'] else None
                av2 = int(row['ask_volume_2']) if row['ask_volume_2'] else 0
                ap3 = float(row['ask_price_3']) if row['ask_price_3'] else None
                av3 = int(row['ask_volume_3']) if row['ask_volume_3'] else 0
                mid = float(row['mid_price']) if row['mid_price'] else None
                rows.append({
                    'ts': ts, 'mid': mid,
                    'bp1': bp1, 'bv1': bv1, 'bp2': bp2, 'bv2': bv2, 'bp3': bp3, 'bv3': bv3,
                    'ap1': ap1, 'av1': av1, 'ap2': ap2, 'av2': av2, 'ap3': ap3, 'av3': av3,
                })
    return rows

def load_trades(day):
    rows = []
    with open(f"trades_round_1_day_{day}.csv") as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row['symbol'] == 'ASH_COATED_OSMIUM':
                rows.append({
                    'ts': int(row['timestamp']),
                    'buyer': row['buyer'],
                    'seller': row['seller'],
                    'price': float(row['price']),
                    'qty': int(row['quantity']),
                })
    return rows

print("=" * 70)
print("ANALYSIS 1: NPC bid/ask level patterns")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # Track all unique bid1 and ask1 values
    bid1_vals = defaultdict(int)
    ask1_vals = defaultdict(int)
    spreads = defaultdict(int)

    for r in prices:
        if r['bp1'] is not None:
            bid1_vals[int(r['bp1'])] += 1
        if r['ap1'] is not None:
            ask1_vals[int(r['ap1'])] += 1
        if r['bp1'] is not None and r['ap1'] is not None:
            s = int(r['ap1'] - r['bp1'])
            spreads[s] += 1

    print(f"Top bid1 values: {sorted(bid1_vals.items(), key=lambda x: -x[1])[:15]}")
    print(f"Top ask1 values: {sorted(ask1_vals.items(), key=lambda x: -x[1])[:15]}")
    print(f"Spread distribution: {sorted(spreads.items(), key=lambda x: -x[1])[:10]}")

print("\n" + "=" * 70)
print("ANALYSIS 2: When spread is NOT 16 - what happens?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    tight_events = []
    for i, r in enumerate(prices):
        if r['bp1'] is not None and r['ap1'] is not None:
            spread = int(r['ap1'] - r['bp1'])
            if spread != 16:
                tight_events.append((i, r))

    print(f"Non-16 spread events: {len(tight_events)} / {len(prices)}")

    # Show first 20
    for idx, (i, r) in enumerate(tight_events[:30]):
        spread = int(r['ap1'] - r['bp1'])
        levels = f"bid={r['bp1']}"
        if r['bp2']: levels += f",{r['bp2']}"
        if r['bp3']: levels += f",{r['bp3']}"
        levels += f" | ask={r['ap1']}"
        if r['ap2']: levels += f",{r['ap2']}"
        if r['ap3']: levels += f",{r['ap3']}"
        print(f"  ts={r['ts']:6d} spread={spread:3d} mid={r['mid']:8.1f} {levels}")

print("\n" + "=" * 70)
print("ANALYSIS 3: Tight spread -> future price movement")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # For each tight spread event, see what mid does over next N ticks
    ts_to_idx = {}
    for i, r in enumerate(prices):
        ts_to_idx[r['ts']] = i

    # Track: at tight spread, was mid above or below 10000? And what happened next?
    results = []
    for i, r in enumerate(prices):
        if r['bp1'] is None or r['ap1'] is None:
            continue
        spread = int(r['ap1'] - r['bp1'])
        if spread < 16 and r['mid'] is not None:
            # Look 5 and 10 ticks ahead
            mid_now = r['mid']
            future_mids = []
            for ahead in [5, 10, 20]:
                if i + ahead < len(prices) and prices[i + ahead]['mid'] is not None:
                    future_mids.append(prices[i + ahead]['mid'] - mid_now)
                else:
                    future_mids.append(None)
            results.append((r['ts'], mid_now, spread, future_mids))

    if results:
        for ts, mid, spr, futs in results[:20]:
            fut_str = ", ".join(f"{f:+.1f}" if f else "N/A" for f in futs)
            print(f"  ts={ts:6d} mid={mid:8.1f} spread={spr} -> [{fut_str}]")

print("\n" + "=" * 70)
print("ANALYSIS 4: NPC trade patterns (buyer/seller empty = NPC)")
print("=" * 70)

for day in [-2, -1, 0]:
    trades = load_trades(day)
    print(f"\n--- Day {day}: {len(trades)} osmium trades ---")

    for t in trades[:40]:
        side = "???"
        if t['buyer'] == '' and t['seller'] == '':
            side = "NPC-NPC"
        elif t['buyer'] == '':
            side = f"NPC buys from {t['seller']}"
        elif t['seller'] == '':
            side = f"{t['buyer']} buys from NPC"
        print(f"  ts={t['ts']:6d} price={t['price']:8.1f} qty={t['qty']:3d} {side}")

print("\n" + "=" * 70)
print("ANALYSIS 5: Is there a sinusoidal pattern in mid prices?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    mids = [(r['ts'], r['mid']) for r in prices if r['mid'] is not None]

    print(f"\n--- Day {day}: {len(mids)} mid observations ---")

    # Detrend by subtracting 10000
    detrended = [(ts, m - 10000) for ts, m in mids]

    # Try fitting sin waves with different periods
    best_corr = 0
    best_period = 0

    for period in range(500, 10001, 100):
        sin_sum = 0
        cos_sum = 0
        n = len(detrended)
        for ts, val in detrended:
            angle = 2 * math.pi * ts / period
            sin_sum += val * math.sin(angle)
            cos_sum += val * math.cos(angle)
        amplitude = math.sqrt(sin_sum**2 + cos_sum**2) / n
        if amplitude > best_corr:
            best_corr = amplitude
            best_period = period

    print(f"  Best sinusoidal fit: period={best_period}, amplitude={best_corr:.2f}")

    # Also try a few specific periods more finely
    for period in range(best_period - 200, best_period + 201, 10):
        if period <= 0:
            continue
        sin_sum = 0
        cos_sum = 0
        n = len(detrended)
        for ts, val in detrended:
            angle = 2 * math.pi * ts / period
            sin_sum += val * math.sin(angle)
            cos_sum += val * math.cos(angle)
        amplitude = math.sqrt(sin_sum**2 + cos_sum**2) / n
        if amplitude > best_corr:
            best_corr = amplitude
            best_period = period

    print(f"  Refined: period={best_period}, amplitude={best_corr:.2f}")

    # Get phase
    sin_sum = 0
    cos_sum = 0
    for ts, val in detrended:
        angle = 2 * math.pi * ts / best_period
        sin_sum += val * math.sin(angle)
        cos_sum += val * math.cos(angle)
    phase = math.atan2(sin_sum, cos_sum)
    print(f"  Phase: {phase:.3f} rad")

print("\n" + "=" * 70)
print("ANALYSIS 6: Mid price at specific timestamps (looking for structure)")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # Sample every 1000 timestamps
    for target_ts in range(0, 100001, 5000):
        for r in prices:
            if r['ts'] == target_ts and r['mid'] is not None:
                print(f"  ts={target_ts:6d} mid={r['mid']:8.1f} dev={r['mid']-10000:+.1f}")
                break

print("\n" + "=" * 70)
print("ANALYSIS 7: Bid/Ask VOLUME patterns")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    vol_patterns = defaultdict(int)
    for r in prices:
        if r['bp1'] is not None and r['ap1'] is not None:
            # Normal pattern is bv1=X, av1=X (symmetric)
            key = (r['bv1'], r['av1'])
            vol_patterns[key] += 1

    print(f"Top (bid_vol1, ask_vol1) patterns:")
    for k, v in sorted(vol_patterns.items(), key=lambda x: -x[1])[:20]:
        print(f"  {k}: {v} times")

print("\n" + "=" * 70)
print("ANALYSIS 8: Does bid1 volume predict next move?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # When volumes are asymmetric, does price move?
    results_by_imb = defaultdict(list)
    for i in range(len(prices) - 1):
        r = prices[i]
        r_next = prices[i+1]
        if r['bp1'] is None or r['ap1'] is None or r['mid'] is None:
            continue
        if r_next['mid'] is None:
            continue

        total_bid_vol = r['bv1'] + r['bv2'] + r['bv3']
        total_ask_vol = r['av1'] + r['av2'] + r['av3']
        if total_bid_vol + total_ask_vol == 0:
            continue

        imb = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)
        ret = r_next['mid'] - r['mid']

        # Bucket imbalance
        bucket = round(imb * 5) / 5  # round to nearest 0.2
        results_by_imb[bucket].append(ret)

    for bucket in sorted(results_by_imb.keys()):
        rets = results_by_imb[bucket]
        avg = sum(rets) / len(rets) if rets else 0
        print(f"  imbalance={bucket:+.1f}: avg_next_ret={avg:+.2f} (n={len(rets)})")

print("\n" + "=" * 70)
print("ANALYSIS 9: Track bid1/ask1 transitions over time")
print("=" * 70)

# This is key - let's see if bid1 and ask1 follow a deterministic sequence
for day in [0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} first 100 ticks ---")

    prev_bp1 = None
    prev_ap1 = None
    for r in prices[:100]:
        bp1 = int(r['bp1']) if r['bp1'] else None
        ap1 = int(r['ap1']) if r['ap1'] else None

        changed = ""
        if prev_bp1 is not None and bp1 != prev_bp1:
            changed += f" bid1:{prev_bp1}->{bp1}"
        if prev_ap1 is not None and ap1 != prev_ap1:
            changed += f" ask1:{prev_ap1}->{ap1}"

        spread = (ap1 - bp1) if (bp1 and ap1) else None
        nlvl = sum(1 for x in [r['bp2'], r['bp3'], r['ap2'], r['ap3']] if x is not None)

        print(f"  ts={r['ts']:6d} bid1={bp1} ask1={ap1} spread={spread} extra_levels={nlvl}{changed}")
        prev_bp1 = bp1
        prev_ap1 = ap1

print("\n" + "=" * 70)
print("ANALYSIS 10: What are the extra levels when they appear?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    for r in prices:
        has_extra = r['bp2'] is not None or r['ap2'] is not None
        if has_extra:
            levels = f"B: {r['bp1']}/{r['bv1']}"
            if r['bp2']: levels += f", {r['bp2']}/{r['bv2']}"
            if r['bp3']: levels += f", {r['bp3']}/{r['bv3']}"
            levels += f" | A: {r['ap1']}/{r['av1']}"
            if r['ap2']: levels += f", {r['ap2']}/{r['av2']}"
            if r['ap3']: levels += f", {r['ap3']}/{r['av3']}"
            spread = int(r['ap1'] - r['bp1']) if (r['bp1'] and r['ap1']) else None
            print(f"  ts={r['ts']:6d} spread={spread} mid={r['mid']:8.1f} {levels}")
