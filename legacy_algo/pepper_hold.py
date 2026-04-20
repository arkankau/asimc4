from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "INTARIAN_PEPPER_ROOT"

    def run(self, state: TradingState):
        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade_pepper(state)
        return result, 0, ""

    def _trade_pepper(self, state: TradingState) -> List[Order]:
        depth = state.order_depths[self.PRODUCT]
        position = state.position.get(self.PRODUCT, 0)
        buy_capacity = self.POSITION_LIMIT - position
        orders: List[Order] = []

        if buy_capacity <= 0:
            return orders

        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_capacity <= 0:
                break
            available = -depth.sell_orders[ask_price]
            if available <= 0:
                continue
            qty = min(available, buy_capacity)
            orders.append(Order(self.PRODUCT, ask_price, qty))
            buy_capacity -= qty

        if buy_capacity > 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders.keys())
            orders.append(Order(self.PRODUCT, best_bid + 1, buy_capacity))

        return orders
