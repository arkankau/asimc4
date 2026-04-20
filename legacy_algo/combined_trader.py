from datamodel import OrderDepth, TradingState, Order
from typing import List
import math


class Trader:
    """Round 1 combined submission: ASH_COATED_OSMIUM MM + INTARIAN_PEPPER_ROOT buy-and-hold."""

    POSITION_LIMIT = 80

    # ASH_COATED_OSMIUM — OU mean reversion around 10000, params from osmium_rainforest.py
    ACO_FAIR = 10001.0
    ACO_TAKE_EDGE = 0.5
    ACO_QUOTE_EDGE = 1.25
    ACO_INV_SKEW = 0.12
    ACO_QUOTE_SIZE = 16

    def run(self, state: TradingState):
        result = {}
        for product in state.order_depths:
            if product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_osmium(state)
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state)
        return result, 0, ""

    def _trade_osmium(self, state: TradingState) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        depth = state.order_depths[product]
        orders: List[Order] = []
        position = state.position.get(product, 0)

        if not depth.buy_orders or not depth.sell_orders:
            return orders

        reservation = self.ACO_FAIR - position * self.ACO_INV_SKEW
        buy_capacity = self.POSITION_LIMIT - position
        sell_capacity = self.POSITION_LIMIT + position

        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_capacity <= 0 or ask_price > reservation - self.ACO_TAKE_EDGE:
                break
            qty = min(buy_capacity, -depth.sell_orders[ask_price])
            if qty > 0:
                orders.append(Order(product, ask_price, qty))
                buy_capacity -= qty

        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if sell_capacity <= 0 or bid_price < reservation + self.ACO_TAKE_EDGE:
                break
            qty = min(sell_capacity, depth.buy_orders[bid_price])
            if qty > 0:
                orders.append(Order(product, bid_price, -qty))
                sell_capacity -= qty

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_quote = min(best_bid + 1, int(math.floor(reservation - self.ACO_QUOTE_EDGE)))
        ask_quote = max(best_ask - 1, int(math.ceil(reservation + self.ACO_QUOTE_EDGE)))

        if bid_quote > 0 and bid_quote < ask_quote and buy_capacity > 0:
            size = min(self.ACO_QUOTE_SIZE, buy_capacity)
            orders.append(Order(product, bid_quote, size))

        if ask_quote > bid_quote and sell_capacity > 0:
            size = min(self.ACO_QUOTE_SIZE, sell_capacity)
            orders.append(Order(product, ask_quote, -size))

        return orders

    def _trade_pepper(self, state: TradingState) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        depth = state.order_depths[product]
        position = state.position.get(product, 0)
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
            orders.append(Order(product, ask_price, qty))
            buy_capacity -= qty

        if buy_capacity > 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders.keys())
            orders.append(Order(product, best_bid + 1, buy_capacity))

        return orders
