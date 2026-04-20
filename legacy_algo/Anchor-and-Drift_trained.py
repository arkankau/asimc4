import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 50,
        "INTARIAN_PEPPER_ROOT": 50,
    }

    ACO_FAIR_VALUE = 10000.0
    ACO_TAKE_EDGE = 0.5
    ACO_QUOTE_EDGE = 3.0
    ACO_INVENTORY_SKEW = 0.20
    ACO_QUOTE_SIZE = 14

    # Historical Round 1 data shows an almost deterministic upward drift.
    IPR_DRIFT_PER_TIMESTAMP = 0.0013
    IPR_MICROPRICE_WEIGHT = 2.5
    IPR_TAKE_EDGE = 3.5
    IPR_BID_QUOTE_EDGE = 3.0
    IPR_ASK_QUOTE_EDGE = 5.0
    IPR_INVENTORY_SKEW = 0.12
    IPR_QUOTE_SIZE = 8

    def run(self, state: TradingState):
        cache = self._load_cache(state.traderData)
        if state.timestamp <= cache.get("last_timestamp", -1):
            cache = {}

        orders: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                orders[product] = self._trade_aco(product, order_depth, state)
            elif product == "INTARIAN_PEPPER_ROOT":
                orders[product] = self._trade_ipr(product, order_depth, state, cache)

        cache["last_timestamp"] = state.timestamp
        trader_data = json.dumps(cache, separators=(",", ":"))
        return orders, 0, trader_data

    def _trade_aco(
        self, product: str, order_depth: OrderDepth, state: TradingState
    ) -> List[Order]:
        best_bid, bid_volume, best_ask, ask_volume = self._best_prices(order_depth)
        if best_bid is None or best_ask is None:
            return []

        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        fair_value = self.ACO_FAIR_VALUE
        reservation_price = fair_value - position * self.ACO_INVENTORY_SKEW

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

    def _trade_ipr(
        self,
        product: str,
        order_depth: OrderDepth,
        state: TradingState,
        cache: Dict,
    ) -> List[Order]:
        best_bid, bid_volume, best_ask, ask_volume = self._best_prices(order_depth)
        if best_bid is None or best_ask is None:
            return []

        mid_price = (best_bid + best_ask) / 2.0
        microprice = self._microprice(best_bid, bid_volume, best_ask, ask_volume)
        micro_dev = 0.0 if microprice is None else microprice - mid_price

        ipr_state = cache.setdefault(
            "ipr",
            {
                "day_open_mid": mid_price,
                "day_open_timestamp": state.timestamp,
            },
        )

        if state.timestamp == 0:
            ipr_state["day_open_mid"] = mid_price
            ipr_state["day_open_timestamp"] = state.timestamp

        trend_fair = (
            ipr_state["day_open_mid"]
            + self.IPR_DRIFT_PER_TIMESTAMP
            * (state.timestamp - ipr_state["day_open_timestamp"])
        )
        fair_value = trend_fair + self.IPR_MICROPRICE_WEIGHT * micro_dev

        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        reservation_price = fair_value - position * self.IPR_INVENTORY_SKEW

        product_orders: List[Order] = []

        position = self._take_asks(
            product,
            order_depth,
            product_orders,
            position,
            limit,
            fair_value - self.IPR_TAKE_EDGE,
        )
        if position > 0:
            position = self._hit_bids(
                product,
                order_depth,
                product_orders,
                position,
                limit,
                fair_value + self.IPR_TAKE_EDGE,
            )

        bid_quote = min(
            best_bid + 1,
            math.floor(reservation_price - self.IPR_BID_QUOTE_EDGE),
        )
        position = self._place_bid_quote(
            product,
            product_orders,
            position,
            limit,
            bid_quote,
            best_ask,
            self._ipr_bid_size(position, limit),
        )

        if position > 0:
            ask_quote = max(
                best_ask - 1,
                math.ceil(reservation_price + self.IPR_ASK_QUOTE_EDGE),
            )
            self._place_ask_quote(
                product,
                product_orders,
                position,
                limit,
                ask_quote,
                best_bid,
                self._ipr_ask_size(position),
            )

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
    ) -> Tuple[Optional[int], int, Optional[int], int]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        bid_volume = order_depth.buy_orders.get(best_bid, 0) if best_bid is not None else 0
        ask_volume = -order_depth.sell_orders.get(best_ask, 0) if best_ask is not None else 0
        return best_bid, bid_volume, best_ask, ask_volume

    def _microprice(
        self,
        best_bid: int,
        bid_volume: int,
        best_ask: int,
        ask_volume: int,
    ) -> Optional[float]:
        total = bid_volume + ask_volume
        if total <= 0:
            return None
        return (best_ask * bid_volume + best_bid * ask_volume) / total

    def _ipr_bid_size(self, position: int, limit: int) -> int:
        remaining = limit - position
        if remaining <= 0:
            return 0
        if position >= limit - 10:
            return min(2, remaining)
        if position >= limit - 20:
            return min(4, remaining)
        return min(self.IPR_QUOTE_SIZE, remaining)

    def _ipr_ask_size(self, position: int) -> int:
        if position <= 0:
            return 0
        if position >= 35:
            return 12
        if position >= 20:
            return 10
        return self.IPR_QUOTE_SIZE

    def _load_cache(self, trader_data: str) -> Dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except json.JSONDecodeError:
            return {}
