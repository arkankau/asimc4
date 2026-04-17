from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "INTARIAN_PEPPER_ROOT"
    MAX_SPREAD = 5  # don't buy asks more than this many ticks above best bid

    def run(self, state: TradingState):
        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade_pepper(state)
        return result, 0, ""

    def _trade_pepper(self, state: TradingState) -> List[Order]:
        order_depth = state.order_depths[self.PRODUCT]
        orders = []
        position = state.position.get(self.PRODUCT, 0)
        buy_capacity = self.POSITION_LIMIT - position

        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        price_cap = (best_bid + self.MAX_SPREAD) if best_bid is not None else float("inf")

        for ask_price in sorted(order_depth.sell_orders.keys()):
            if buy_capacity <= 0 or ask_price > price_cap:
                break
            qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
            orders.append(Order(self.PRODUCT, ask_price, qty))
            buy_capacity -= qty

        if buy_capacity > 0 and best_bid is not None:
            orders.append(Order(self.PRODUCT, best_bid + 1, buy_capacity))

        return orders
