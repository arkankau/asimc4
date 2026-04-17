import json
from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "INTARIAN_PEPPER_ROOT"
    DRAWDOWN = 30  # ticks below peak mid before we start unwinding

    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            memory = {}

        peak = memory.get("peak", None)

        order_depth = state.order_depths.get(self.PRODUCT)
        mid = None
        if order_depth and order_depth.buy_orders and order_depth.sell_orders:
            mid = (max(order_depth.buy_orders.keys()) + min(order_depth.sell_orders.keys())) / 2
            peak = mid if peak is None else max(peak, mid)

        in_drawdown = (mid is not None and peak is not None and peak - mid >= self.DRAWDOWN)

        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade_pepper(state, in_drawdown)

        memory["peak"] = peak
        return result, 0, json.dumps(memory)

    def _trade_pepper(self, state: TradingState, in_drawdown: bool) -> List[Order]:
        order_depth = state.order_depths[self.PRODUCT]
        orders = []
        position = state.position.get(self.PRODUCT, 0)

        if not in_drawdown:
            # Normal: accumulate to max long
            buy_capacity = self.POSITION_LIMIT - position
            for ask_price in sorted(order_depth.sell_orders.keys()):
                if buy_capacity <= 0:
                    break
                qty = min(buy_capacity, -order_depth.sell_orders[ask_price])
                orders.append(Order(self.PRODUCT, ask_price, qty))
                buy_capacity -= qty
            if buy_capacity > 0 and order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())
                orders.append(Order(self.PRODUCT, best_bid + 1, buy_capacity))
        else:
            # Drawdown triggered: sell everything into bids
            sell_capacity = position
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if sell_capacity <= 0:
                    break
                qty = min(sell_capacity, order_depth.buy_orders[bid_price])
                orders.append(Order(self.PRODUCT, bid_price, -qty))
                sell_capacity -= qty
            if sell_capacity > 0 and order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())
                orders.append(Order(self.PRODUCT, best_ask - 1, -sell_capacity))

        return orders
