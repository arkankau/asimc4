from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    POSITION_LIMIT = 80

    # Fixed fair value - osmium mean-reverts tightly around 10000
    FAIR_VALUE = 10000

    # How much to skew our quotes per unit of position (inventory risk mgmt)
    # Positive position -> lower our fair to incentivize selling
    POSITION_SKEW = 0.15

    # Threshold: only take NPC quotes that are this far past fair value
    # (otherwise the spread cost eats the reversion profit)
    TAKE_THRESHOLD = 2

    # When tight spread detected (extra NPC in book), be more aggressive
    TIGHT_SPREAD_THRESHOLD = 14  # spreads < 14 signal extra NPC activity

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(state, trader_data)

        return result, 0, json.dumps(trader_data)

    def _load_data(self, raw: str) -> dict:
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return {"last_mid": None}

    def _trade_osmium(self, state: TradingState, data: dict) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        od = state.order_depths[product]
        orders: List[Order] = []
        position = state.position.get(product, 0)
        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position

        if not od.sell_orders and not od.buy_orders:
            return orders

        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else (best_bid or best_ask)

        # Track last mid for reversal signal
        last_mid = data.get("last_mid")
        data["last_mid"] = mid

        # Compute our adjusted fair value with position skew
        # When we're long, lower fair to be more eager to sell
        # When we're short, raise fair to be more eager to buy
        fair = self.FAIR_VALUE - position * self.POSITION_SKEW

        # Detect tight spread (extra NPC in the book)
        spread = (best_ask - best_bid) if (best_ask and best_bid) else 999
        tight_spread = spread < self.TIGHT_SPREAD_THRESHOLD

        # Compute reversal signal from last tick
        last_delta = (mid - last_mid) if last_mid is not None else 0

        # --- LAYER 1: Take mispriced NPC levels ---
        # Buy asks that are below our fair value (accounting for threshold)
        take_fair = fair - self.TAKE_THRESHOLD if not tight_spread else fair
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price >= take_fair or buy_cap <= 0:
                break
            qty = min(buy_cap, -od.sell_orders[ask_price])
            orders.append(Order(product, ask_price, qty))
            buy_cap -= qty

        # Sell bids that are above our fair value (accounting for threshold)
        take_fair_sell = fair + self.TAKE_THRESHOLD if not tight_spread else fair
        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price <= take_fair_sell or sell_cap <= 0:
                break
            qty = min(sell_cap, od.buy_orders[bid_price])
            orders.append(Order(product, bid_price, -qty))
            sell_cap -= qty

        # --- LAYER 2: During tight spread, trade into the mean-reversion ---
        if tight_spread and best_bid and best_ask:
            if mid < self.FAIR_VALUE - 2 and buy_cap > 0:
                # Price is below fair, tight spread = extra NPC selling
                # Buy aggressively at the tight ask
                for ask_price in sorted(od.sell_orders.keys()):
                    if buy_cap <= 0 or ask_price > self.FAIR_VALUE:
                        break
                    qty = min(buy_cap, -od.sell_orders[ask_price])
                    orders.append(Order(product, ask_price, qty))
                    buy_cap -= qty

            elif mid > self.FAIR_VALUE + 2 and sell_cap > 0:
                # Price is above fair, tight spread = extra NPC buying
                # Sell aggressively at the tight bid
                for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                    if sell_cap <= 0 or bid_price < self.FAIR_VALUE:
                        break
                    qty = min(sell_cap, od.buy_orders[bid_price])
                    orders.append(Order(product, bid_price, -qty))
                    sell_cap -= qty

        # --- LAYER 3: Post resting quotes inside the spread ---
        if best_bid and best_ask:
            our_bid = best_bid + 1
            our_ask = best_ask - 1

            # Shift toward fair value: don't post on wrong side
            # Also use reversal signal to lean
            if last_delta > 0:
                # Price just went up, expect down -> lean short
                our_ask = max(our_ask - 1, int(fair) + 1)
            elif last_delta < 0:
                # Price just went down, expect up -> lean long
                our_bid = min(our_bid + 1, int(fair) - 1)

            # Post quotes if they're on the correct side of our fair
            if our_bid < fair and buy_cap > 0:
                orders.append(Order(product, our_bid, buy_cap))
            if our_ask > fair and sell_cap > 0:
                orders.append(Order(product, our_ask, -sell_cap))

        return orders
