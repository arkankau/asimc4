from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:
    """ASH_COATED_OSMIUM mean-reversion market maker.

    Params grid-searched on round 1 days -2/-1/0 via train_osmium_rainforest.py.
    Backtested PnL: ~46.8k over 3 days (15.3k / 16.3k / 15.3k).
    """

    POSITION_LIMIT = 80

    FAIR_VALUE = 10001.0
    TAKE_EDGE = 0.5
    QUOTE_EDGE = 1.25
    INV_SKEW = 0.12
    QUOTE_SIZE = 16

    def run(self, state: TradingState):
        result = {}
        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(state)
        return result, 0, ""

    def _trade_osmium(self, state: TradingState) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        depth = state.order_depths[product]
        orders: List[Order] = []
        position = state.position.get(product, 0)

        if not depth.buy_orders or not depth.sell_orders:
            return orders

        reservation = self.FAIR_VALUE - position * self.INV_SKEW
        buy_capacity = self.POSITION_LIMIT - position
        sell_capacity = self.POSITION_LIMIT + position

        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_capacity <= 0 or ask_price > reservation - self.TAKE_EDGE:
                break
            qty = min(buy_capacity, -depth.sell_orders[ask_price])
            if qty > 0:
                orders.append(Order(product, ask_price, qty))
                buy_capacity -= qty

        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if sell_capacity <= 0 or bid_price < reservation + self.TAKE_EDGE:
                break
            qty = min(sell_capacity, depth.buy_orders[bid_price])
            if qty > 0:
                orders.append(Order(product, bid_price, -qty))
                sell_capacity -= qty

        best_bid = max(depth.buy_orders.keys())
        best_ask = min(depth.sell_orders.keys())

        bid_quote = min(best_bid + 1, int(math.floor(reservation - self.QUOTE_EDGE)))
        ask_quote = max(best_ask - 1, int(math.ceil(reservation + self.QUOTE_EDGE)))

        if bid_quote > 0 and bid_quote < ask_quote and buy_capacity > 0:
            size = min(self.QUOTE_SIZE, buy_capacity)
            orders.append(Order(product, bid_quote, size))

        if ask_quote > bid_quote and sell_capacity > 0:
            size = min(self.QUOTE_SIZE, sell_capacity)
            orders.append(Order(product, ask_quote, -size))

        return orders
