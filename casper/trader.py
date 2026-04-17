from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            if product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state)
            elif product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_osmium(state)

        return result, 0, ""

    # -------------------------------------------------------------------------
    # INTARIAN_PEPPER_ROOT
    # Price trends up ~0.1 XIREC per timestamp (~+1000/day).
    # Strategy: always hold max long position (80).
    # -------------------------------------------------------------------------

    def _trade_pepper(self, state: TradingState) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        order_depth = state.order_depths[product]
        orders = []
        position = state.position.get(product, 0)
        buy_capacity = self.POSITION_LIMIT - position

        # Take all available asks immediately
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if buy_capacity <= 0:
                break
            qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
            orders.append(Order(product, ask_price, qty))
            buy_capacity -= qty

        # Post a bid one tick above best bot bid to fill remaining capacity
        if buy_capacity > 0 and order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            orders.append(Order(product, best_bid + 1, buy_capacity))

        return orders

    # -------------------------------------------------------------------------
    # ASH_COATED_OSMIUM
    # Mean-reverts around ~10000. Described as "volatile with hidden pattern".
    # Strategy: market-make inside bot spread; take any cross-fair-value quotes.
    # -------------------------------------------------------------------------

    def _trade_osmium(self, state: TradingState) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        order_depth = state.order_depths[product]
        orders = []
        position = state.position.get(product, 0)
        buy_capacity = self.POSITION_LIMIT - position
        sell_capacity = self.POSITION_LIMIT + position

        fair_value = 10000

        # Take any bot quotes that already cross fair value (rare but free money)
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price >= fair_value or buy_capacity <= 0:
                break
            qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
            orders.append(Order(product, ask_price, qty))
            buy_capacity -= qty

        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price <= fair_value or sell_capacity <= 0:
                break
            qty = min(sell_capacity, order_depth.buy_orders[bid_price])
            orders.append(Order(product, bid_price, -qty))
            sell_capacity -= qty

        # Post resting quotes one tick inside the bot spread
        if order_depth.sell_orders and order_depth.buy_orders:
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            our_bid = best_bid + 1
            our_ask = best_ask - 1

            # Only quote if our prices are still on the correct side of fair value
            # and the spread is wide enough to be profitable
            if our_bid < fair_value and our_ask > fair_value and our_ask > our_bid:
                if buy_capacity > 0:
                    orders.append(Order(product, our_bid, buy_capacity))
                if sell_capacity > 0:
                    orders.append(Order(product, our_ask, -sell_capacity))

        return orders
