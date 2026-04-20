import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    ACO_FAIR_VALUE = 10000.0
    ACO_TAKE_EDGE = 1.0
    ACO_QUOTE_EDGE = 3.0
    ACO_INVENTORY_SKEW = 0.20
    ACO_QUOTE_SIZE = 12

    def run(self, state: TradingState):
        orders: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                orders[product] = self._trade_aco(product, order_depth, state)
            elif product == "INTARIAN_PEPPER_ROOT":
                orders[product] = self._trade_ipr_buy_and_hold(product, order_depth, state)

        return orders, 0, ""

    def _trade_aco(
        self, product: str, order_depth: OrderDepth, state: TradingState
    ) -> List[Order]:
        best_bid, best_ask = self._best_prices(order_depth)
        if best_bid is None or best_ask is None:
            return []

        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        reservation_price = self.ACO_FAIR_VALUE - position * self.ACO_INVENTORY_SKEW

        product_orders: List[Order] = []

        position = self._take_asks(
            product,
            order_depth,
            product_orders,
            position,
            limit,
            reservation_price - self.ACO_TAKE_EDGE,
        )
        position = self._hit_bids(
            product,
            order_depth,
            product_orders,
            position,
            limit,
            reservation_price + self.ACO_TAKE_EDGE,
        )

        bid_quote = min(best_bid + 1, math.floor(reservation_price - self.ACO_QUOTE_EDGE))
        ask_quote = max(best_ask - 1, math.ceil(reservation_price + self.ACO_QUOTE_EDGE))

        position = self._place_bid_quote(
            product,
            product_orders,
            position,
            limit,
            bid_quote,
            best_ask,
            self.ACO_QUOTE_SIZE,
        )
        self._place_ask_quote(
            product,
            product_orders,
            position,
            limit,
            ask_quote,
            best_bid,
            self.ACO_QUOTE_SIZE,
        )

        return product_orders

    def _trade_ipr_buy_and_hold(
        self, product: str, order_depth: OrderDepth, state: TradingState
    ) -> List[Order]:
        # Price drifts +0.001/tick continuously across days. Hold max long for full round.
        # Final MTM at round end captures the drift × position.
        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        buy_capacity = limit - position
        if buy_capacity <= 0:
            return []

        product_orders: List[Order] = []

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            available = -ask_volume
            if available <= 0:
                continue
            qty = min(available, buy_capacity)
            product_orders.append(Order(product, ask_price, qty))
            buy_capacity -= qty

        if buy_capacity > 0 and order_depth.buy_orders:
            best_bid = max(order_depth.buy_orders.keys())
            product_orders.append(Order(product, best_bid + 1, buy_capacity))

        return product_orders

    def _take_asks(
        self,
        product: str,
        order_depth: OrderDepth,
        product_orders: List[Order],
        position: int,
        limit: int,
        max_buy_price: float,
    ) -> int:
        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            available = -ask_volume
            if available <= 0 or ask_price > max_buy_price or position >= limit:
                break
            buy_quantity = min(available, limit - position)
            if buy_quantity <= 0:
                break
            product_orders.append(Order(product, ask_price, buy_quantity))
            position += buy_quantity
        return position

    def _hit_bids(
        self,
        product: str,
        order_depth: OrderDepth,
        product_orders: List[Order],
        position: int,
        limit: int,
        min_sell_price: float,
    ) -> int:
        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if bid_volume <= 0 or bid_price < min_sell_price or position <= -limit:
                break
            sell_quantity = min(bid_volume, position + limit)
            if sell_quantity <= 0:
                break
            product_orders.append(Order(product, bid_price, -sell_quantity))
            position -= sell_quantity
        return position

    def _place_bid_quote(
        self,
        product: str,
        product_orders: List[Order],
        position: int,
        limit: int,
        bid_quote: int,
        best_ask: Optional[int],
        size: int,
    ) -> int:
        remaining = limit - position
        if remaining <= 0:
            return position
        if best_ask is not None and bid_quote >= best_ask:
            bid_quote = best_ask - 1
        if bid_quote <= 0:
            return position
        quote_size = min(size, remaining)
        if quote_size > 0:
            product_orders.append(Order(product, bid_quote, quote_size))
            position += quote_size
        return position

    def _place_ask_quote(
        self,
        product: str,
        product_orders: List[Order],
        position: int,
        limit: int,
        ask_quote: int,
        best_bid: Optional[int],
        size: int,
    ) -> int:
        remaining = limit + position
        if remaining <= 0:
            return position
        if best_bid is not None and ask_quote <= best_bid:
            ask_quote = best_bid + 1
        quote_size = min(size, remaining)
        if quote_size > 0:
            product_orders.append(Order(product, ask_quote, -quote_size))
            position -= quote_size
        return position

    def _best_prices(
        self, order_depth: OrderDepth
    ) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask
