from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "ASH_COATED_OSMIUM"
    FAIR_VALUE = 10000

    def run(self, state: TradingState):
        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade_osmium(state)
        return result, 0, ""

    # -------------------------------------------------------------------------
    # ASH_COATED_OSMIUM
    # Mean-reverts around ~10000. Described as "volatile with hidden pattern".
    # Strategy: market-make inside bot spread; take any cross-fair-value quotes.
    # -------------------------------------------------------------------------

    def _trade_osmium(self, state: TradingState) -> List[Order]:
        order_depth = state.order_depths[self.PRODUCT]
        orders = []
        position = state.position.get(self.PRODUCT, 0)
        buy_capacity = self.POSITION_LIMIT - position
        sell_capacity = self.POSITION_LIMIT + position

        # Take any bot quotes that already cross fair value (rare but free money)
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price >= self.FAIR_VALUE or buy_capacity <= 0:
                break
            qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
            orders.append(Order(self.PRODUCT, ask_price, qty))
            buy_capacity -= qty

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price <= self.FAIR_VALUE or sell_capacity <= 0:
                break
            qty = min(sell_capacity, order_depth.buy_orders[bid_price])
            orders.append(Order(self.PRODUCT, bid_price, -qty))
            sell_capacity -= qty

        # Post resting quotes one tick inside the bot spread
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            our_bid = best_bid + 1
            our_ask = best_ask - 1

            if our_bid < self.FAIR_VALUE and our_ask > self.FAIR_VALUE and our_ask > our_bid:
                if buy_capacity > 0:
                    orders.append(Order(self.PRODUCT, our_bid, buy_capacity))
                if sell_capacity > 0:
                    orders.append(Order(self.PRODUCT, our_ask, -sell_capacity))

        return orders
