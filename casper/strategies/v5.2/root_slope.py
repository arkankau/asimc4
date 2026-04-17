import json
from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    POSITION_LIMIT = 80
    PRODUCT = "INTARIAN_PEPPER_ROOT"
    WINDOW = 150      # long enough to smooth intra-trend noise
    SLOPE_MIN = 0.01  # ticks/timestamp to stay long
    CONFIRM_TICKS = 30  # slope must stay below SLOPE_MIN this many consecutive ticks before unwinding

    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            memory = {}

        prices = memory.get("prices", [])
        below_count = memory.get("below_count", 0)  # consecutive ticks slope < SLOPE_MIN

        order_depth = state.order_depths.get(self.PRODUCT)
        if order_depth and order_depth.buy_orders and order_depth.sell_orders:
            mid = (max(order_depth.buy_orders.keys()) + min(order_depth.sell_orders.keys())) / 2
            prices.append(mid)
            if len(prices) > self.WINDOW:
                prices = prices[-self.WINDOW:]

        slope = self._slope(prices)

        if slope < self.SLOPE_MIN:
            below_count += 1
        else:
            below_count = 0  # reset on any positive tick

        # Only commit to unwind after CONFIRM_TICKS consecutive weak slope readings
        trend_lost = below_count >= self.CONFIRM_TICKS

        result = {}
        if self.PRODUCT in state.order_depths:
            result[self.PRODUCT] = self._trade_pepper(state, trend_lost)

        memory["prices"] = prices
        memory["below_count"] = below_count
        return result, 0, json.dumps(memory)

    def _slope(self, prices: list) -> float:
        n = len(prices)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        num = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0

    def _trade_pepper(self, state: TradingState, trend_lost: bool) -> List[Order]:
        order_depth = state.order_depths[self.PRODUCT]
        orders = []
        position = state.position.get(self.PRODUCT, 0)

        if not trend_lost:
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
