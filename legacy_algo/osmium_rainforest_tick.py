from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import math


class Trader:
    """ASH_COATED_OSMIUM mean-reversion market maker with spread-adaptive quoting.

    Params grid-searched on round 1 days -2/-1/0 via train_osmium_rainforest.py
    and train_osmium_adaptive.py.

    Baseline (non-adaptive) backtest PnL: ~46.8k over 3 days.
    With wide-spread adaptation (quote 3 ticks inside when spread >= 18): ~50.0k.
    """

    POSITION_LIMIT = 80

    FAIR_VALUE = 10001.0
    TAKE_EDGE = 0.5
    QUOTE_EDGE = 1.25
    INV_SKEW = 0.12
    QUOTE_SIZE = 16

    # Spread-regime adaptation: when spread is wide, step deeper inside the book.
    # Rationale: data spread distribution is peaked at 16 (64%) with a heavy tail
    # at 18-20 (25%). Pennying an 18-wide spread only captures the outer edge;
    # stepping 3 ticks inside still leaves us alone at top of book but closer to
    # fair, increasing fill rate enough to beat the edge cost.
    WIDE_SPREAD_THRESHOLD = 18
    WIDE_INSIDE_OFFSET = 3

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
        spread = best_ask - best_bid
        inside_offset = self.WIDE_INSIDE_OFFSET if spread >= self.WIDE_SPREAD_THRESHOLD else 1

        bid_quote = min(best_bid + inside_offset, int(math.floor(reservation - self.QUOTE_EDGE)))
        ask_quote = max(best_ask - inside_offset, int(math.ceil(reservation + self.QUOTE_EDGE)))

        if bid_quote > 0 and bid_quote < ask_quote and buy_capacity > 0:
            size = min(self.QUOTE_SIZE, buy_capacity)
            orders.append(Order(product, bid_quote, size))

        if ask_quote > bid_quote and sell_capacity > 0:
            size = min(self.QUOTE_SIZE, sell_capacity)
            orders.append(Order(product, ask_quote, -size))

        return orders
