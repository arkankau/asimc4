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

    # -------------------------------------------------------------------------
    # INTARIAN_PEPPER_ROOT
    # Price trends up ~0.1 XIREC per timestamp (~+1000/day).
    # Strategy: always hold max long position (80).
    # -------------------------------------------------------------------------

    def _trade_pepper(self, state: TradingState) -> List[Order]:
        order_depth = state.order_depths[self.PRODUCT]
        orders = []
        position = state.position.get(self.PRODUCT, 0)
        buy_capacity = self.POSITION_LIMIT - position

        # Take all available asks immediately
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if buy_capacity <= 0:
                break
            qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
            orders.append(Order(self.PRODUCT, ask_price, qty))
            buy_capacity -= qty

        # Post a bid one tick above best bot bid to fill remaining capacity
        if buy_capacity > 0 and order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            orders.append(Order(self.PRODUCT, best_bid + 1, buy_capacity))

        return orders
