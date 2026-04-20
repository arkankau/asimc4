import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Optional


class Trader:
    """
    v10 — v9b IPR (slope gate + aggressive fill) + v12 ACO (EMA + position skew).
    IPR: no buy-price cap, fills aggressively at ask from tick 0.
    ACO: position skew=0.05 (lighter than v12's 0.10, backtests better on R2).
    """

    POSITION_LIMIT = 80

    IPR = "INTARIAN_PEPPER_ROOT"
    IPR_WINDOW = 150
    IPR_SLOPE_MIN = 0.01
    IPR_CONFIRM_TICKS = 30

    ACO = "ASH_COATED_OSMIUM"
    ACO_EMA_ALPHA = 0.002
    ACO_WARMUP = 50
    ACO_POSITION_SKEW = 0.05

    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            memory = {}

        result = {}

        if self.IPR in state.order_depths:
            result[self.IPR], memory = self._trade_ipr(state, memory)

        if self.ACO in state.order_depths:
            result[self.ACO], memory = self._trade_aco(state, memory)

        return result, 0, json.dumps(memory)

    def _trade_ipr(self, state: TradingState, memory: dict):
        prices = memory.get("ipr_prices", [])
        below_count = memory.get("ipr_below", 0)

        od = state.order_depths[self.IPR]
        if od.buy_orders and od.sell_orders:
            mid = (max(od.buy_orders) + min(od.sell_orders)) / 2
            prices.append(mid)
            if len(prices) > self.IPR_WINDOW:
                prices = prices[-self.IPR_WINDOW:]

        slope = self._slope(prices)
        below_count = below_count + 1 if slope < self.IPR_SLOPE_MIN else 0
        trend_lost = below_count >= self.IPR_CONFIRM_TICKS

        orders = []
        position = state.position.get(self.IPR, 0)

        if not trend_lost:
            buy_cap = self.POSITION_LIMIT - position
            for ask in sorted(od.sell_orders):
                if buy_cap <= 0:
                    break
                qty = min(buy_cap, -od.sell_orders[ask])
                orders.append(Order(self.IPR, ask, qty))
                buy_cap -= qty
            if buy_cap > 0 and od.buy_orders:
                orders.append(Order(self.IPR, max(od.buy_orders) + 1, buy_cap))
        else:
            sell_cap = position
            for bid in sorted(od.buy_orders, reverse=True):
                if sell_cap <= 0:
                    break
                qty = min(sell_cap, od.buy_orders[bid])
                orders.append(Order(self.IPR, bid, -qty))
                sell_cap -= qty
            if sell_cap > 0 and od.sell_orders:
                orders.append(Order(self.IPR, min(od.sell_orders) - 1, -sell_cap))

        memory["ipr_prices"] = prices
        memory["ipr_below"] = below_count
        return orders, memory

    def _trade_aco(self, state: TradingState, memory: dict):
        od = state.order_depths[self.ACO]
        orders = []

        if not od.buy_orders or not od.sell_orders:
            return orders, memory

        mid = (max(od.buy_orders) + min(od.sell_orders)) / 2
        aco_ticks = memory.get("aco_ticks", 0)
        fv = memory.get("aco_fv", mid)
        fv = (1 - self.ACO_EMA_ALPHA) * fv + self.ACO_EMA_ALPHA * mid
        aco_ticks += 1
        memory["aco_fv"] = fv
        memory["aco_ticks"] = aco_ticks

        if aco_ticks < self.ACO_WARMUP:
            return orders, memory

        position = state.position.get(self.ACO, 0)
        fair = fv - position * self.ACO_POSITION_SKEW

        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position

        for ask in sorted(od.sell_orders):
            if ask >= fair or buy_cap <= 0:
                break
            qty = min(buy_cap, abs(od.sell_orders[ask]))
            orders.append(Order(self.ACO, ask, qty))
            buy_cap -= qty

        for bid in sorted(od.buy_orders, reverse=True):
            if bid <= fair or sell_cap <= 0:
                break
            qty = min(sell_cap, od.buy_orders[bid])
            orders.append(Order(self.ACO, bid, -qty))
            sell_cap -= qty

        our_bid = max(od.buy_orders) + 1
        our_ask = min(od.sell_orders) - 1

        if buy_cap > 0 and our_bid < fair:
            orders.append(Order(self.ACO, our_bid, buy_cap))
        if sell_cap > 0 and our_ask > fair:
            orders.append(Order(self.ACO, our_ask, -sell_cap))

        return orders, memory

    def _slope(self, prices: list) -> float:
        n = len(prices)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        num = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0
