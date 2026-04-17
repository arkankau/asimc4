from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:
    """
    Osmium strategy combining market-making with contra-trend positions at extremes.

    Normal mode: market-make 1 tick inside bot spread (same as v3).
    Extreme mode: when |mid - 10000| > EXTREME_THRESHOLD, add contra-trend resting
    order closer to fair value to capture the near-certain reversion.
    (Data: ±10 -> 74.9% revert, ±15 -> 95% revert next tick)
    """

    POSITION_LIMIT = 80
    PRODUCT = "ASH_COATED_OSMIUM"
    FAIR_VALUE = 10000
    EXTREME_THRESHOLD = 10   # deviation from 10000 to enter extreme mode
    SKEW_THRESHOLD = 40      # don't add inventory on heavy side beyond this

    def run(self, state: TradingState):
        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade(state)
        return result, 0, ""

    def _trade(self, state: TradingState) -> List[Order]:
        od = state.order_depths[self.PRODUCT]
        orders = []
        pos = state.position.get(self.PRODUCT, 0)
        buy_cap = self.POSITION_LIMIT - pos
        sell_cap = self.POSITION_LIMIT + pos

        if not od.buy_orders or not od.sell_orders:
            return orders

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        mid = (best_bid + best_ask) / 2
        fv = self.FAIR_VALUE
        dev = mid - fv

        # Aggressive takes on any quote crossing fair value
        for ask in sorted(od.sell_orders):
            if ask >= fv or buy_cap <= 0:
                break
            qty = min(buy_cap, -od.sell_orders[ask])
            orders.append(Order(self.PRODUCT, ask, qty))
            buy_cap -= qty

        for bid in sorted(od.buy_orders, reverse=True):
            if bid <= fv or sell_cap <= 0:
                break
            qty = min(sell_cap, od.buy_orders[bid])
            orders.append(Order(self.PRODUCT, bid, -qty))
            sell_cap -= qty

        our_bid = best_bid + 1
        our_ask = best_ask - 1

        if abs(dev) >= self.EXTREME_THRESHOLD:
            if dev > 0:
                # Price above fair: near-certain drop coming — prioritise selling
                # Post ask tighter (2 ticks inside spread) to capture reversion
                our_ask = best_ask - 2
                if sell_cap > 0:
                    orders.append(Order(self.PRODUCT, our_ask, -sell_cap))
                # Only buy if we're not already long
                if buy_cap > 0 and pos < self.SKEW_THRESHOLD and our_bid < fv:
                    orders.append(Order(self.PRODUCT, our_bid, buy_cap))
            else:
                # Price below fair: near-certain rise coming — prioritise buying
                our_bid = best_bid + 2
                if buy_cap > 0:
                    orders.append(Order(self.PRODUCT, our_bid, buy_cap))
                # Only sell if we're not already short
                if sell_cap > 0 and pos > -self.SKEW_THRESHOLD and our_ask > fv:
                    orders.append(Order(self.PRODUCT, our_ask, -sell_cap))
        else:
            # Normal mode: symmetric market-make inside bot spread
            if our_bid < fv and our_ask > fv and our_ask > our_bid:
                if buy_cap > 0 and pos < self.SKEW_THRESHOLD:
                    orders.append(Order(self.PRODUCT, our_bid, buy_cap))
                if sell_cap > 0 and pos > -self.SKEW_THRESHOLD:
                    orders.append(Order(self.PRODUCT, our_ask, -sell_cap))

        return orders
