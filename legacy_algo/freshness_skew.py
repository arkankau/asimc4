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
    ACO_TAKE_EDGE = 1.5
    ACO_QUOTE_EDGE = 2.5
    ACO_INVENTORY_SKEW = 0.10
    ACO_QUOTE_SIZE = 10
    ACO_MICROPRICE_WEIGHT = 0.0
    ACO_OFI_WEIGHT = 0.0
    ACO_STALE_DECAY = 0.35
    ACO_STALE_WIDEN = 1.4
    ACO_STALE_HALT_STEPS = 5

    IPR_DRIFT_PER_TIMESTAMP = 0.00135
    IPR_TAKE_EDGE = 2.5
    IPR_BID_QUOTE_EDGE = 3.5
    IPR_ASK_QUOTE_EDGE = 7.0
    IPR_INVENTORY_SKEW = 0.08
    IPR_QUOTE_SIZE = 8
    IPR_MICROPRICE_WEIGHT = 2.5
    IPR_OFI_WEIGHT = 0.5
    IPR_STALE_DECAY = 0.10
    IPR_STALE_WIDEN = 1.4
    IPR_STALE_HALT_STEPS = 2

    def run(self, state: TradingState):
        cache = self._load_cache(state.traderData)
        if state.timestamp <= cache.get("last_timestamp", -1):
            cache = {}

        orders: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            product_state = cache.setdefault(product, {})
            if product == "ASH_COATED_OSMIUM":
                orders[product] = self._trade_aco(product, order_depth, state, product_state)
            elif product == "INTARIAN_PEPPER_ROOT":
                orders[product] = self._trade_ipr(product, order_depth, state, product_state)

        cache["last_timestamp"] = state.timestamp
        return orders, 0, json.dumps(cache, separators=(",", ":"))

    def _trade_aco(
        self,
        product: str,
        order_depth: OrderDepth,
        state: TradingState,
        product_state: Dict,
    ) -> List[Order]:
        book = self._extract_book(order_depth)
        if book is None:
            return []

        best_bid, bid_volume, best_ask, ask_volume = book
        mid_price = (best_bid + best_ask) / 2.0
        micro_dev = self._micro_dev(best_bid, bid_volume, best_ask, ask_volume)
        stale_steps = self._stale_steps(state.timestamp, product_state.get("last_valid_timestamp"))
        signal = self._signal_shift(
            book,
            product_state.get("last_book"),
            micro_dev,
            self.ACO_MICROPRICE_WEIGHT,
            self.ACO_OFI_WEIGHT,
            self.ACO_STALE_DECAY,
            stale_steps,
        )

        fair_value = self.ACO_FAIR_VALUE + signal
        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        reservation_price = fair_value - position * self.ACO_INVENTORY_SKEW
        product_orders: List[Order] = []

        if stale_steps < self.ACO_STALE_HALT_STEPS:
            position = self._take_asks(
                product,
                order_depth,
                product_orders,
                position,
                limit,
                fair_value - self.ACO_TAKE_EDGE,
            )
            position = self._hit_bids(
                product,
                order_depth,
                product_orders,
                position,
                limit,
                fair_value + self.ACO_TAKE_EDGE,
            )

        quote_edge = self.ACO_QUOTE_EDGE + self.ACO_STALE_WIDEN * stale_steps
        bid_quote = min(best_bid + 1, math.floor(reservation_price - quote_edge))
        ask_quote = max(best_ask - 1, math.ceil(reservation_price + quote_edge))

        if stale_steps < self.ACO_STALE_HALT_STEPS or position < 0:
            position = self._place_bid_quote(
                product,
                product_orders,
                position,
                limit,
                bid_quote,
                best_ask,
                self.ACO_QUOTE_SIZE,
            )
        if stale_steps < self.ACO_STALE_HALT_STEPS or position > 0:
            self._place_ask_quote(
                product,
                product_orders,
                position,
                limit,
                ask_quote,
                best_bid,
                self.ACO_QUOTE_SIZE,
            )

        product_state["last_valid_timestamp"] = state.timestamp
        product_state["last_book"] = [best_bid, bid_volume, best_ask, ask_volume]
        return product_orders

    def _trade_ipr(
        self,
        product: str,
        order_depth: OrderDepth,
        state: TradingState,
        product_state: Dict,
    ) -> List[Order]:
        book = self._extract_book(order_depth)
        if book is None:
            return []

        best_bid, bid_volume, best_ask, ask_volume = book
        mid_price = (best_bid + best_ask) / 2.0
        micro_dev = self._micro_dev(best_bid, bid_volume, best_ask, ask_volume)
        stale_steps = self._stale_steps(state.timestamp, product_state.get("last_valid_timestamp"))

        if "day_open_mid" not in product_state or state.timestamp == 0:
            product_state["day_open_mid"] = mid_price
            product_state["day_open_timestamp"] = state.timestamp

        trend_fair = (
            product_state["day_open_mid"]
            + self.IPR_DRIFT_PER_TIMESTAMP
            * (state.timestamp - product_state["day_open_timestamp"])
        )
        signal = self._signal_shift(
            book,
            product_state.get("last_book"),
            micro_dev,
            self.IPR_MICROPRICE_WEIGHT,
            self.IPR_OFI_WEIGHT,
            self.IPR_STALE_DECAY,
            stale_steps,
        )
        fair_value = trend_fair + signal

        position = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        reservation_price = fair_value - position * self.IPR_INVENTORY_SKEW
        product_orders: List[Order] = []

        if stale_steps < self.IPR_STALE_HALT_STEPS:
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

        bid_quote_edge = self.IPR_BID_QUOTE_EDGE + self.IPR_STALE_WIDEN * stale_steps
        bid_quote = min(best_bid + 1, math.floor(reservation_price - bid_quote_edge))
        if stale_steps < self.IPR_STALE_HALT_STEPS:
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
            ask_quote_edge = self.IPR_ASK_QUOTE_EDGE + self.IPR_STALE_WIDEN * stale_steps
            ask_quote = max(best_ask - 1, math.ceil(reservation_price + ask_quote_edge))
            self._place_ask_quote(
                product,
                product_orders,
                position,
                limit,
                ask_quote,
                best_bid,
                self._ipr_ask_size(position),
            )

        product_state["last_valid_timestamp"] = state.timestamp
        product_state["last_book"] = [best_bid, bid_volume, best_ask, ask_volume]
        return product_orders

    def _extract_book(
        self, order_depth: OrderDepth
    ) -> Optional[Tuple[int, int, int, int]]:
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        bid_volume = order_depth.buy_orders.get(best_bid, 0)
        ask_volume = -order_depth.sell_orders.get(best_ask, 0)
        if best_bid <= 0 or best_ask <= 0 or best_bid >= best_ask:
            return None
        if bid_volume <= 0 or ask_volume <= 0:
            return None
        return best_bid, bid_volume, best_ask, ask_volume

    def _micro_dev(
        self,
        best_bid: int,
        bid_volume: int,
        best_ask: int,
        ask_volume: int,
    ) -> float:
        total = bid_volume + ask_volume
        if total <= 0:
            return 0.0
        microprice = (best_ask * bid_volume + best_bid * ask_volume) / total
        return microprice - (best_bid + best_ask) / 2.0

    def _stale_steps(self, timestamp: int, last_valid_timestamp: Optional[int]) -> int:
        if last_valid_timestamp is None:
            return 0
        return max(0, (timestamp - last_valid_timestamp) // 100 - 1)

    def _signal_shift(
        self,
        book: Tuple[int, int, int, int],
        last_book: Optional[List[int]],
        micro_dev: float,
        micro_weight: float,
        ofi_weight: float,
        stale_decay: float,
        stale_steps: int,
    ) -> float:
        ofi_norm = self._normalized_ofi(book, last_book)
        freshness = math.exp(-stale_decay * stale_steps)
        return freshness * (micro_weight * micro_dev + ofi_weight * ofi_norm)

    def _normalized_ofi(
        self,
        book: Tuple[int, int, int, int],
        last_book: Optional[List[int]],
    ) -> float:
        if not last_book:
            return 0.0

        bid, bid_volume, ask, ask_volume = book
        prev_bid, prev_bid_volume, prev_ask, prev_ask_volume = last_book

        ofi = 0.0
        if bid > prev_bid:
            ofi += bid_volume
        elif bid == prev_bid:
            ofi += bid_volume - prev_bid_volume
        else:
            ofi -= prev_bid_volume

        if ask < prev_ask:
            ofi += prev_ask_volume
        elif ask == prev_ask:
            ofi += prev_ask_volume - ask_volume
        else:
            ofi -= ask_volume

        scale = max(
            1.0,
            (bid_volume + ask_volume + prev_bid_volume + prev_ask_volume) / 2.0,
        )
        return ofi / scale

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
