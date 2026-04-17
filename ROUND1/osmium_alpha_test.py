"""Test specific alpha hypotheses for osmium."""
import csv
from collections import defaultdict

def load_prices(day):
    rows = []
    with open(f"prices_round_1_day_{day}.csv") as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row['product'] == 'ASH_COATED_OSMIUM':
                ts = int(row['timestamp'])
                bp1 = float(row['bid_price_1']) if row['bid_price_1'] else None
                ap1 = float(row['ask_price_1']) if row['ask_price_1'] else None
                mid = float(row['mid_price']) if row['mid_price'] else None
                bv1 = int(row['bid_volume_1']) if row['bid_volume_1'] else 0
                av1 = int(row['ask_volume_1']) if row['ask_volume_1'] else 0
                rows.append({'ts': ts, 'mid': mid, 'bp1': bp1, 'ap1': ap1, 'bv1': bv1, 'av1': av1})
    return rows

print("=" * 70)
print("HYPOTHESIS 1: Fade-the-move (tick-by-tick reversal)")
print("=" * 70)
print()

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"--- Day {day} ---")

    # Track consecutive up/down moves and what happens next
    deltas = []
    for i in range(1, len(prices)):
        if prices[i]['mid'] is not None and prices[i-1]['mid'] is not None:
            d = prices[i]['mid'] - prices[i-1]['mid']
            deltas.append((prices[i]['ts'], d, prices[i]['mid']))

    # After a move of size X, what's the next move?
    reversal_by_size = defaultdict(lambda: {'reverse': 0, 'continue': 0, 'flat': 0, 'rev_total': 0, 'cont_total': 0})
    for i in range(len(deltas) - 1):
        d = deltas[i][1]
        d_next = deltas[i+1][1]
        if d == 0:
            continue
        bucket = round(abs(d))
        if bucket == 0:
            continue
        direction = 1 if d > 0 else -1
        if d_next * direction < 0:
            reversal_by_size[bucket]['reverse'] += 1
            reversal_by_size[bucket]['rev_total'] += abs(d_next)
        elif d_next * direction > 0:
            reversal_by_size[bucket]['continue'] += 1
            reversal_by_size[bucket]['cont_total'] += abs(d_next)
        else:
            reversal_by_size[bucket]['flat'] += 1

    for size in sorted(reversal_by_size.keys()):
        r = reversal_by_size[size]
        total = r['reverse'] + r['continue'] + r['flat']
        rev_pct = r['reverse'] / total * 100 if total else 0
        avg_rev = r['rev_total'] / r['reverse'] if r['reverse'] else 0
        avg_cont = r['cont_total'] / r['continue'] if r['continue'] else 0
        print(f"  |move|={size:2d}: reversal={rev_pct:5.1f}% (n={total:4d}) "
              f"avg_rev_size={avg_rev:.1f} avg_cont_size={avg_cont:.1f}")
    print()

print("=" * 70)
print("HYPOTHESIS 2: Position-aware quoting strategy simulation")
print("=" * 70)
print()

# Simulate: after each tick, fade the last move
# Buy at best_ask when last move was DOWN
# Sell at best_bid when last move was UP
# Track PnL

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"--- Day {day} ---")

    position = 0
    cash = 0
    LIMIT = 80

    trades = 0
    for i in range(2, len(prices)):
        prev = prices[i-1]
        curr = prices[i]
        prev2 = prices[i-2]

        if curr['mid'] is None or prev['mid'] is None or prev2['mid'] is None:
            continue
        if curr['bp1'] is None or curr['ap1'] is None:
            continue

        last_delta = prev['mid'] - prev2['mid']

        if last_delta < 0 and position < LIMIT:
            # Price went down, expect reversal UP -> BUY
            buy_qty = min(10, LIMIT - position)  # conservative size
            if buy_qty > 0:
                price = int(curr['ap1'])
                position += buy_qty
                cash -= price * buy_qty
                trades += 1

        elif last_delta > 0 and position > -LIMIT:
            # Price went up, expect reversal DOWN -> SELL
            sell_qty = min(10, LIMIT + position)
            if sell_qty > 0:
                price = int(curr['bp1'])
                position -= sell_qty
                cash += price * sell_qty
                trades += 1

    # Mark to market at end
    final_mid = None
    for r in reversed(prices):
        if r['mid'] is not None:
            final_mid = r['mid']
            break
    mtm = cash + position * final_mid if final_mid else cash
    print(f"  Aggressive fade: trades={trades}, pos={position}, cash={cash:.0f}, MTM PnL={mtm:.0f}")

    # Now simulate conservative: only post inside spread, don't cross
    position = 0
    cash = 0
    fills = 0

    for i in range(2, len(prices)):
        prev = prices[i-1]
        curr = prices[i]
        prev2 = prices[i-2]

        if curr['mid'] is None or prev['mid'] is None or prev2['mid'] is None:
            continue
        if curr['bp1'] is None or curr['ap1'] is None:
            continue
        if prev['bp1'] is None or prev['ap1'] is None:
            continue

        last_delta = prev['mid'] - prev2['mid']

        # We posted orders last tick, check if they would have filled
        # Our bid would fill if curr ask <= our bid
        # Our ask would fill if curr bid >= our ask

        # Post inside spread: bid = best_bid + 1, ask = best_ask - 1
        our_bid = int(prev['bp1']) + 1
        our_ask = int(prev['ap1']) - 1

        # Skew based on last move direction
        if last_delta > 0:  # was up, lean short
            our_bid -= 1  # less eager to buy
            our_ask -= 1  # more eager to sell
        elif last_delta < 0:  # was down, lean long
            our_bid += 1  # more eager to buy
            our_ask += 1  # less eager to sell

        # Check fills
        if curr['ap1'] is not None and curr['ap1'] <= our_bid and position < LIMIT:
            qty = min(10, LIMIT - position)
            position += qty
            cash -= our_bid * qty
            fills += 1

        if curr['bp1'] is not None and curr['bp1'] >= our_ask and position > -LIMIT:
            qty = min(10, LIMIT + position)
            position -= qty
            cash += our_ask * qty
            fills += 1

    final_mid = None
    for r in reversed(prices):
        if r['mid'] is not None:
            final_mid = r['mid']
            break
    mtm = cash + position * final_mid if final_mid else cash
    print(f"  Passive fade: fills={fills}, pos={position}, cash={cash:.0f}, MTM PnL={mtm:.0f}")
    print()


print("=" * 70)
print("HYPOTHESIS 3: The mid price follows bid1+8/ask1-8 pattern")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # Check: is mid always exactly (bid1+ask1)/2?
    # And is spread always divisible by 2?
    spread_vals = defaultdict(int)
    mid_offset = defaultdict(int)
    for r in prices:
        if r['bp1'] is not None and r['ap1'] is not None:
            spread = r['ap1'] - r['bp1']
            spread_vals[spread] += 1
            calc_mid = (r['bp1'] + r['ap1']) / 2
            offset = calc_mid - 10000
            mid_offset[round(offset)] += 1

    print(f"Spread values (exact): {sorted(spread_vals.items(), key=lambda x: -x[1])[:10]}")
    print(f"Mid offset from 10000: {sorted(mid_offset.items(), key=lambda x: x[0])[:20]}")


print("\n" + "=" * 70)
print("HYPOTHESIS 4: Distance from 10000 predicts next return direction")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    results = defaultdict(list)
    for i in range(len(prices) - 1):
        if prices[i]['mid'] is None or prices[i+1]['mid'] is None:
            continue
        dev = prices[i]['mid'] - 10000
        ret = prices[i+1]['mid'] - prices[i]['mid']
        bucket = round(dev / 3) * 3  # bucket by 3
        results[bucket].append(ret)

    for bucket in sorted(results.keys()):
        rets = results[bucket]
        if len(rets) < 5:
            continue
        avg = sum(rets) / len(rets)
        pos_pct = sum(1 for r in rets if r > 0) / len(rets) * 100
        print(f"  dev={bucket:+3d}: avg_next={avg:+.3f} up%={pos_pct:.0f}% (n={len(rets)})")


print("\n" + "=" * 70)
print("HYPOTHESIS 5: Spread changes predict next move")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # When spread changes from 16 to something else, what happens to mid?
    results = defaultdict(list)
    for i in range(1, len(prices) - 5):
        prev = prices[i-1]
        curr = prices[i]
        if prev['bp1'] is None or prev['ap1'] is None:
            continue
        if curr['bp1'] is None or curr['ap1'] is None:
            continue

        prev_spread = prev['ap1'] - prev['bp1']
        curr_spread = curr['ap1'] - curr['bp1']

        if prev_spread == 16 and curr_spread != 16:
            # Spread just changed from 16!
            future_rets = []
            for ahead in [1, 3, 5]:
                if i + ahead < len(prices) and prices[i + ahead]['mid'] is not None and curr['mid'] is not None:
                    future_rets.append(prices[i + ahead]['mid'] - curr['mid'])
                else:
                    future_rets.append(None)

            dev = curr['mid'] - 10000 if curr['mid'] else 0
            results[round(curr_spread)].append((dev, future_rets))

    for spread in sorted(results.keys()):
        events = results[spread]
        if len(events) < 3:
            continue
        avg_devs = sum(e[0] for e in events) / len(events)
        avg_ret1 = sum(e[1][0] for e in events if e[1][0] is not None) / max(1, sum(1 for e in events if e[1][0] is not None))
        avg_ret5 = sum(e[1][2] for e in events if e[1][2] is not None) / max(1, sum(1 for e in events if e[1][2] is not None))
        print(f"  spread 16->{spread}: avg_dev={avg_devs:+.1f} avg_ret1={avg_ret1:+.2f} avg_ret5={avg_ret5:+.2f} (n={len(events)})")


print("\n" + "=" * 70)
print("HYPOTHESIS 6: Microprice signal")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # microprice = (bid * ask_vol + ask * bid_vol) / (bid_vol + ask_vol)
    results = defaultdict(list)
    for i in range(len(prices) - 1):
        r = prices[i]
        r_next = prices[i+1]
        if r['bp1'] is None or r['ap1'] is None or r_next['mid'] is None or r['mid'] is None:
            continue
        if r['bv1'] + r['av1'] == 0:
            continue

        microprice = (r['bp1'] * r['av1'] + r['ap1'] * r['bv1']) / (r['bv1'] + r['av1'])
        mp_signal = microprice - r['mid']  # positive = microprice above mid = bullish
        ret = r_next['mid'] - r['mid']

        bucket = round(mp_signal)
        results[bucket].append(ret)

    for bucket in sorted(results.keys()):
        rets = results[bucket]
        if len(rets) < 5:
            continue
        avg = sum(rets) / len(rets)
        print(f"  microprice_signal={bucket:+3d}: avg_next_ret={avg:+.3f} (n={len(rets)})")


print("\n" + "=" * 70)
print("HYPOTHESIS 7: Combined signal (deviation from 10000 + last return)")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    results = defaultdict(list)
    for i in range(1, len(prices) - 1):
        if prices[i-1]['mid'] is None or prices[i]['mid'] is None or prices[i+1]['mid'] is None:
            continue

        dev = prices[i]['mid'] - 10000
        last_ret = prices[i]['mid'] - prices[i-1]['mid']
        next_ret = prices[i+1]['mid'] - prices[i]['mid']

        dev_bucket = "far_above" if dev > 5 else ("above" if dev > 0 else ("below" if dev < -5 else "near" if dev >= -5 else "far_below"))
        ret_bucket = "up" if last_ret > 0 else ("down" if last_ret < 0 else "flat")

        key = f"{dev_bucket}/{ret_bucket}"
        results[key].append(next_ret)

    for key in sorted(results.keys()):
        rets = results[key]
        if len(rets) < 10:
            continue
        avg = sum(rets) / len(rets)
        up_pct = sum(1 for r in rets if r > 0) / len(rets) * 100
        print(f"  {key:25s}: avg_next={avg:+.3f} up%={up_pct:.0f}% (n={len(rets)})")


print("\n" + "=" * 70)
print("HYPOTHESIS 8: What if we ONLY market-make, never cross spread?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # Simulate pure market-making: always post bid at best_bid+1, ask at best_ask-1
    # Check how often our orders would get filled
    position = 0
    cash = 0
    fills_buy = 0
    fills_sell = 0
    LIMIT = 80

    # Track our posted orders
    for i in range(1, len(prices)):
        prev = prices[i-1]
        curr = prices[i]

        if prev['bp1'] is None or prev['ap1'] is None:
            continue
        if curr['bp1'] is None or curr['ap1'] is None:
            continue

        # We posted orders last tick
        our_bid = int(prev['bp1']) + 1
        our_ask = int(prev['ap1']) - 1

        # Our bid fills if the current best ask <= our bid (someone sold to us)
        # In practice, this happens when the mid drops enough that our bid becomes attractive
        # Actually in Prosperity, our orders are matched against incoming orders
        # If a bot places a sell order at or below our bid, we get filled

        # Proxy: our bid fills if the current tick's lowest trade price <= our_bid
        # Since we don't have tick-level trade data, approximate:
        # Our bid fills if current mid < prev mid (price dropped, MM's ask might cross our bid)
        # Better proxy: our bid fills if current ap1 <= our_bid (extremely tight)
        # This is too conservative. In Prosperity, if we post bid at 9993+1=9994 and
        # the MM changes bid to 9993 (ask to 10009), our 9994 bid is ABOVE the new bid
        # but below the new ask (10009). So we don't get filled.
        # We only get filled if someone actively sells at our price.

        # Actually the best proxy: look at when the book moved DOWN
        mid_change = (curr['mid'] - prev['mid']) if (curr['mid'] and prev['mid']) else 0

        # If mid went down, it means sell pressure. Our bid MIGHT have been hit.
        # If mid went up, buy pressure. Our ask MIGHT have been hit.
        # This is a rough estimate.

        # Let's just compute the theoretical PnL from the "fair value approach"
        # Fair value = 10000
        # If we can buy below 10000 and sell above 10000, we profit
        pass

    # Simple theoretical: how much time does mid spend above vs below 10000?
    above = below = at = 0
    for r in prices:
        if r['mid'] is None:
            continue
        if r['mid'] > 10000:
            above += 1
        elif r['mid'] < 10000:
            below += 1
        else:
            at += 1
    total = above + below + at
    print(f"  Mid > 10000: {above/total*100:.1f}%, Mid < 10000: {below/total*100:.1f}%, At 10000: {at/total*100:.1f}%")

    # Average mid
    mids = [r['mid'] for r in prices if r['mid'] is not None]
    avg_mid = sum(mids) / len(mids)
    print(f"  Average mid: {avg_mid:.2f}")

    # Key: count how many times mid CROSSES 10000
    crosses = 0
    for i in range(1, len(prices)):
        if prices[i]['mid'] is None or prices[i-1]['mid'] is None:
            continue
        if (prices[i]['mid'] - 10000) * (prices[i-1]['mid'] - 10000) < 0:
            crosses += 1
    print(f"  Crosses 10000: {crosses} times")


print("\n" + "=" * 70)
print("HYPOTHESIS 9: Is the spread size the signal?")
print("=" * 70)

for day in [-2, -1, 0]:
    prices = load_prices(day)
    print(f"\n--- Day {day} ---")

    # When spread < 16, what side of 10000 is the price on?
    # And does it predict direction?
    tight_above = 0
    tight_below = 0
    tight_above_drops = 0
    tight_below_rises = 0

    for i in range(len(prices) - 5):
        r = prices[i]
        if r['bp1'] is None or r['ap1'] is None:
            continue
        spread = r['ap1'] - r['bp1']
        if spread < 14 and r['mid'] is not None:
            # Tight spread event
            future_mid = None
            for j in range(i+1, min(i+10, len(prices))):
                if prices[j]['mid'] is not None:
                    future_mid = prices[j]['mid']
                    break

            if future_mid is None:
                continue

            if r['mid'] > 10000:
                tight_above += 1
                if future_mid < r['mid']:
                    tight_above_drops += 1
            elif r['mid'] < 10000:
                tight_below += 1
                if future_mid > r['mid']:
                    tight_below_rises += 1

    print(f"  Tight spread + above 10000: {tight_above}, drops after: {tight_above_drops} ({tight_above_drops/max(1,tight_above)*100:.0f}%)")
    print(f"  Tight spread + below 10000: {tight_below}, rises after: {tight_below_rises} ({tight_below_rises/max(1,tight_below)*100:.0f}%)")
