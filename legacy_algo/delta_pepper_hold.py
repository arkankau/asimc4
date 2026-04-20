from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:
    """One-shot delta strategy for INTARIAN_PEPPER_ROOT.

    State machine (persisted in traderData):
      waiting_buy -> holding -> done

    - On the first tick where mid rises vs the previous tick: go max long.
    - On the first tick AFTER entry where mid falls vs the previous tick: flatten to 0.
    - After that: idle for the rest of the session.
    """

    POSITION_LIMIT = 80
    PRODUCT = "INTARIAN_PEPPER_ROOT"

    def run(self, state: TradingState):
        memory = self._load(state.traderData)
        orders: List[Order] = []

        depth = state.order_depths.get(self.PRODUCT)
        if depth is not None and depth.buy_orders and depth.sell_orders:
            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())
            mid = (best_bid + best_ask) / 2.0

            last_mid = memory.get("last_mid")
            phase = memory.get("phase", "waiting_buy")
            position = state.position.get(self.PRODUCT, 0)

            if last_mid is not None:
                delta = mid - last_mid

                if phase == "waiting_buy" and delta > 0:
                    orders = self._buy_to_limit(depth, position)
                    phase = "holding"
                elif phase == "holding" and delta < 0:
                    orders = self._sell_to_zero(depth, position)
                    phase = "done"

            memory["last_mid"] = mid
            memory["phase"] = phase

        return {self.PRODUCT: orders}, 0, json.dumps(memory)

    def _buy_to_limit(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        buy_capacity = self.POSITION_LIMIT - position
        if buy_capacity <= 0:
            return orders

        for ask_price in sorted(depth.sell_orders.keys()):
            if buy_capacity <= 0:
                break
            available = -depth.sell_orders[ask_price]
            if available <= 0:
                continue
            qty = min(available, buy_capacity)
            orders.append(Order(self.PRODUCT, ask_price, qty))
            buy_capacity -= qty

        if buy_capacity > 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders.keys())
            orders.append(Order(self.PRODUCT, best_bid + 1, buy_capacity))

        return orders

    def _sell_to_zero(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        if position <= 0:
            return orders

        to_sell = position
        for bid_price in sorted(depth.buy_orders.keys(), reverse=True):
            if to_sell <= 0:
                break
            available = depth.buy_orders[bid_price]
            if available <= 0:
                continue
            qty = min(available, to_sell)
            orders.append(Order(self.PRODUCT, bid_price, -qty))
            to_sell -= qty

        if to_sell > 0 and depth.sell_orders:
            best_ask = min(depth.sell_orders.keys())
            orders.append(Order(self.PRODUCT, best_ask - 1, -to_sell))

        return orders

    def _load(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}
