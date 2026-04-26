from __future__ import annotations

import json
from typing import List

try:
    from datamodel import Order, OrderDepth, Trade, TradingState
except ModuleNotFoundError:
    from imc_backtester.datamodel import Order, OrderDepth, Trade, TradingState


class Trader:
    PRODUCT = "INTARIAN_PEPPER_ROOT"
    POSITION_LIMIT = 80

    DRIFT_PER_TICK = 0.001
    ANCHOR_ALPHA = 0.02

    OLIVIA_SIZE = 8
    SIGNAL_EDGE = 2.5
    BUY_SIGNAL_HOLD = 8
    SELL_SIGNAL_HOLD = 4

    BASE_TARGET = 80
    BUY_SIGNAL_TARGET = 80
    SELL_SIGNAL_TARGET = 60

    def bid(self) -> int:
        return 15

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        orders: List[Order] = []

        depth = state.order_depths.get(self.PRODUCT)
        if depth is not None:
            orders, memory = self._trade_pepper(state, depth, memory)

        return {self.PRODUCT: orders}, 0, json.dumps(memory, separators=(",", ":"))

    def _trade_pepper(self, state: TradingState, depth: OrderDepth, memory: dict) -> tuple[List[Order], dict]:
        if not depth.buy_orders or not depth.sell_orders:
            return [], memory

        mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        anchor = memory.get("anchor")
        raw_anchor = mid - self.DRIFT_PER_TICK * state.timestamp
        if anchor is None:
            anchor = raw_anchor
        else:
            anchor = (1.0 - self.ANCHOR_ALPHA) * float(anchor) + self.ANCHOR_ALPHA * raw_anchor
        fair = anchor + self.DRIFT_PER_TICK * state.timestamp
        memory["anchor"] = anchor

        score = self._olivia_score(state.market_trades.get(self.PRODUCT, []), anchor)
        active_until = int(memory.get("active_until", -1))
        active_target = int(memory.get("active_target", self.BASE_TARGET))

        if score > 0:
            active_until = state.timestamp + self.BUY_SIGNAL_HOLD * 100
            active_target = self.BUY_SIGNAL_TARGET
        elif score < 0:
            active_until = state.timestamp + self.SELL_SIGNAL_HOLD * 100
            active_target = self.SELL_SIGNAL_TARGET

        memory["active_until"] = active_until
        memory["active_target"] = active_target
        memory["last_score"] = score

        target = active_target if state.timestamp <= active_until else self.BASE_TARGET
        position = state.position.get(self.PRODUCT, 0)
        return self._move_to_target(depth, position, target, fair), memory

    def _olivia_score(self, trades: List[Trade], anchor: float) -> int:
        score = 0
        for trade in trades:
            if trade.quantity != self.OLIVIA_SIZE:
                continue

            trade_fair = anchor + self.DRIFT_PER_TICK * trade.timestamp
            if trade_fair - trade.price >= self.SIGNAL_EDGE:
                score += 1
            elif trade.price - trade_fair >= self.SIGNAL_EDGE:
                score -= 1
        return score

    def _move_to_target(self, depth: OrderDepth, position: int, target: int, fair: float) -> List[Order]:
        orders: List[Order] = []

        if target > position:
            buy_capacity = min(target - position, self.POSITION_LIMIT - position)
            remaining = buy_capacity
            for ask_price in sorted(depth.sell_orders):
                available = -depth.sell_orders[ask_price]
                if remaining <= 0 or available <= 0:
                    break
                qty = min(remaining, available)
                orders.append(Order(self.PRODUCT, ask_price, qty))
                remaining -= qty

            if remaining > 0 and depth.buy_orders:
                best_bid = max(depth.buy_orders)
                quote = min(best_bid + 1, int(round(fair)))
                orders.append(Order(self.PRODUCT, quote, remaining))

        elif target < position:
            sell_capacity = min(position - target, self.POSITION_LIMIT + position)
            remaining = sell_capacity
            for bid_price in sorted(depth.buy_orders, reverse=True):
                available = depth.buy_orders[bid_price]
                if remaining <= 0 or available <= 0:
                    break
                qty = min(remaining, available)
                orders.append(Order(self.PRODUCT, bid_price, -qty))
                remaining -= qty

            if remaining > 0 and depth.sell_orders:
                best_ask = min(depth.sell_orders)
                quote = max(best_ask - 1, int(round(fair)))
                orders.append(Order(self.PRODUCT, quote, -remaining))

        return orders

    def _load_memory(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
