from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "ASH_COATED_OSMIUM"
    FAIR_VALUE = 10000
    SKEW_THRESHOLD = 40   # above this abs position, stop adding to the heavy side
    UNWIND_THRESHOLD = 65 # above this, actively reduce by posting tighter on unwinding side

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
        fv = self.FAIR_VALUE

        # Aggressive takes: cross fair value only
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
        if our_bid >= fv or our_ask <= fv or our_ask <= our_bid:
            return orders

        # Skew: if position is too long, don't add more bids; if too short, don't add more asks
        want_bid = pos < self.SKEW_THRESHOLD
        want_ask = pos > -self.SKEW_THRESHOLD

        # Unwind mode: if very long, post ask tighter (best_ask - 2) to get filled faster
        if pos >= self.UNWIND_THRESHOLD:
            our_ask = best_ask - 2
            want_bid = False
        elif pos <= -self.UNWIND_THRESHOLD:
            our_bid = best_bid + 2
            want_ask = False

        if want_bid and buy_cap > 0:
            orders.append(Order(self.PRODUCT, our_bid, buy_cap))
        if want_ask and sell_cap > 0:
            orders.append(Order(self.PRODUCT, our_ask, -sell_cap))

        return orders
