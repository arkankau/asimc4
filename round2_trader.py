from __future__ import annotations

import math
from typing import List

try:
    from datamodel import Order, OrderDepth, TradingState
except ModuleNotFoundError:
    from imc_backtester.datamodel import Order, OrderDepth, TradingState


class Trader:
    """
    Round 2 playbook:
    - INTARIAN_PEPPER_ROOT: structural long, fill to the limit and stay there.
    - ASH_COATED_OSMIUM: simple anchored market making around 10_001.
    """

    POSITION_LIMIT = 80

    IPR = "INTARIAN_PEPPER_ROOT"
    ACO = "ASH_COATED_OSMIUM"

    ACO_FAIR = 10001.0
    ACO_TAKE_EDGE = 1.0
    ACO_QUOTE_EDGE = 3.0
    ACO_INV_SKEW = 0.12
    ACO_IMBALANCE_SKEW = 2.0
    ACO_QUOTE_SIZE = 16

    def run(self, state: TradingState):
        result = {}

        ipr_depth = state.order_depths.get(self.IPR)
        if ipr_depth is not None:
            result[self.IPR] = self._trade_ipr(ipr_depth, state.position.get(self.IPR, 0))

        aco_depth = state.order_depths.get(self.ACO)
        if aco_depth is not None:
            result[self.ACO] = self._trade_aco(aco_depth, state.position.get(self.ACO, 0))

        return result, 0, ""

    def _trade_ipr(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        buy_capacity = self.POSITION_LIMIT - position
        if buy_capacity <= 0:
            return orders

        for ask_price in sorted(depth.sell_orders):
            available = -depth.sell_orders[ask_price]
            if available <= 0 or buy_capacity <= 0:
                continue
            quantity = min(available, buy_capacity)
            orders.append(Order(self.IPR, ask_price, quantity))
            buy_capacity -= quantity

        if buy_capacity > 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            orders.append(Order(self.IPR, best_bid + 1, buy_capacity))

        return orders

    def _trade_aco(self, depth: OrderDepth, position: int) -> List[Order]:
        if not depth.buy_orders or not depth.sell_orders:
            return []

        orders: List[Order] = []

        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        bid_volume = max(0, depth.buy_orders[best_bid])
        ask_volume = max(0, -depth.sell_orders[best_ask])

        denom = bid_volume + ask_volume
        imbalance = (bid_volume - ask_volume) / denom if denom > 0 else 0.0
        reservation = self.ACO_FAIR + self.ACO_IMBALANCE_SKEW * imbalance - position * self.ACO_INV_SKEW

        buy_capacity = self.POSITION_LIMIT - position
        sell_capacity = self.POSITION_LIMIT + position

        for ask_price in sorted(depth.sell_orders):
            if buy_capacity <= 0 or ask_price > reservation - self.ACO_TAKE_EDGE:
                break
            quantity = min(buy_capacity, -depth.sell_orders[ask_price])
            if quantity <= 0:
                continue
            orders.append(Order(self.ACO, ask_price, quantity))
            buy_capacity -= quantity

        for bid_price in sorted(depth.buy_orders, reverse=True):
            if sell_capacity <= 0 or bid_price < reservation + self.ACO_TAKE_EDGE:
                break
            quantity = min(sell_capacity, depth.buy_orders[bid_price])
            if quantity <= 0:
                continue
            orders.append(Order(self.ACO, bid_price, -quantity))
            sell_capacity -= quantity

        bid_quote = min(best_bid + 1, math.floor(reservation - self.ACO_QUOTE_EDGE))
        ask_quote = max(best_ask - 1, math.ceil(reservation + self.ACO_QUOTE_EDGE))

        if buy_capacity > 0 and bid_quote > 0 and bid_quote < best_ask:
            orders.append(Order(self.ACO, bid_quote, min(self.ACO_QUOTE_SIZE, buy_capacity)))

        if sell_capacity > 0 and ask_quote > best_bid:
            orders.append(Order(self.ACO, ask_quote, -min(self.ACO_QUOTE_SIZE, sell_capacity)))

        return orders
