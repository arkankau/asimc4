from datamodel import OrderDepth, Order, TradingState
from typing import Any, Dict, List, Optional, Tuple
import json
import math


class Trader:
    POSITION_LIMIT = 80

    # Pepper parameters - robust trend-following with staged de-risking
    PEPPER_HISTORY = 160
    PEPPER_SHORT_WINDOW = 24
    PEPPER_LONG_WINDOW = 96
    PEPPER_SLOPE_WINDOW = 48
    PEPPER_WEAK_CONFIRM = 6
    PEPPER_BREAK_CONFIRM = 4
    PEPPER_CORE_TARGET = POSITION_LIMIT // 2
    PEPPER_WARMUP_TARGET = 60
    PEPPER_PASSIVE_SIZE = 20

    # Osmium parameters - dynamic wall-fair market making / distortion fading
    OSMIUM_POSITION_SKEW = 0.10
    OSMIUM_VALUE_TAKE_THRESHOLD = 2
    OSMIUM_DISTORTED_SPREAD = 13
    OSMIUM_PASSIVE_SIZE = 20
    OSMIUM_PREFERRED_SPREADS = (16, 18, 19, 21)

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self._trade_pepper(state, trader_data["pepper"])
        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(state, trader_data["osmium"])

        return result, 0, json.dumps(trader_data)

    def _load_data(self, raw: str) -> Dict[str, Dict[str, Any]]:
        parsed: Dict[str, Any] = {}
        if raw:
            try:
                candidate = json.loads(raw)
                if isinstance(candidate, dict):
                    parsed = candidate
            except (json.JSONDecodeError, TypeError):
                parsed = {}

        pepper_blob = parsed.get("pepper")
        if not isinstance(pepper_blob, dict):
            pepper_blob = {
                "prices": parsed.get("pepper_prices", []),
                "peak": parsed.get("pepper_peak"),
                "weak_count": parsed.get("pepper_weak_count", 0),
                "break_count": parsed.get("pepper_break_count", 0),
            }

        osmium_blob = parsed.get("osmium")
        if not isinstance(osmium_blob, dict):
            osmium_blob = {
                "last_mid": parsed.get("last_mid"),
                "last_wall_fair": parsed.get("last_wall_fair"),
            }

        prices = pepper_blob.get("prices", [])
        if not isinstance(prices, list):
            prices = []

        return {
            "pepper": {
                "prices": prices[-self.PEPPER_HISTORY :],
                "peak": pepper_blob.get("peak"),
                "weak_count": int(pepper_blob.get("weak_count", 0) or 0),
                "break_count": int(pepper_blob.get("break_count", 0) or 0),
            },
            "osmium": {
                "last_mid": osmium_blob.get("last_mid"),
                "last_wall_fair": osmium_blob.get("last_wall_fair"),
            },
        }

    def _trade_pepper(self, state: TradingState, data: Dict[str, Any]) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        od = state.order_depths[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        mid = self._mid_price(od)
        if mid is None:
            return orders

        prices = data.get("prices", [])
        prices.append(mid)
        prices = prices[-self.PEPPER_HISTORY :]
        data["prices"] = prices

        peak = data.get("peak")
        if position <= 0 or peak is None:
            peak = mid
        else:
            peak = max(float(peak), mid)
        data["peak"] = peak

        short_ma = self._window_mean(prices, self.PEPPER_SHORT_WINDOW)
        long_ma = self._window_mean(prices, self.PEPPER_LONG_WINDOW)
        slope = self._window_slope(prices, self.PEPPER_SLOPE_WINDOW)
        avg_abs_ret = self._avg_abs_return(prices, self.PEPPER_SLOPE_WINDOW)
        spread = self._spread(od, default=4.0)

        trail = max(8.0, 6.0 * avg_abs_ret + spread)
        strong_trend = short_ma >= long_ma and slope > 0 and mid >= short_ma - spread / 2.0
        weakening = short_ma < long_ma or slope <= 0
        broken_trend = (
            short_ma + max(1.0, avg_abs_ret) < long_ma
            or slope < -0.25 * max(1.0, avg_abs_ret)
            or peak - mid > trail
        )

        weak_count = int(data.get("weak_count", 0))
        break_count = int(data.get("break_count", 0))
        weak_count = weak_count + 1 if weakening else max(0, weak_count - 1)
        break_count = break_count + 1 if broken_trend else 0
        data["weak_count"] = weak_count
        data["break_count"] = break_count

        if len(prices) < self.PEPPER_SHORT_WINDOW // 2:
            target = self.PEPPER_WARMUP_TARGET
        elif break_count >= self.PEPPER_BREAK_CONFIRM:
            target = 0
        elif strong_trend:
            target = self.POSITION_LIMIT
        elif weak_count >= self.PEPPER_WEAK_CONFIRM:
            target = self.PEPPER_CORE_TARGET if slope >= 0 else 0
        else:
            target = self.PEPPER_CORE_TARGET

        drift_bonus = max(0.0, slope) * min(12, max(1, len(prices) // 8))
        fair = max(mid, short_ma) + drift_bonus
        if break_count >= self.PEPPER_BREAK_CONFIRM:
            fair = min(mid, short_ma)

        buy_cap = max(0, target - position)
        sell_cap = max(0, position - target)
        bought = 0
        sold = 0

        # De-risk first when the trend has clearly broken.
        if sell_cap > 0:
            exit_floor = fair - (0 if break_count >= self.PEPPER_BREAK_CONFIRM else 1)
            for bid in sorted(od.buy_orders, reverse=True):
                if sell_cap - sold <= 0:
                    break
                if break_count < self.PEPPER_BREAK_CONFIRM and bid < exit_floor:
                    break
                qty = min(od.buy_orders[bid], sell_cap - sold)
                if qty <= 0:
                    continue
                orders.append(Order(product, bid, -qty))
                sold += qty

        # If the book is stretched well above our fair estimate, rotate back to core size.
        rotation_floor = self.PEPPER_CORE_TARGET if strong_trend else target
        if position + bought - sold > rotation_floor and od.buy_orders:
            rotation_trigger = fair + max(1.0, spread / 2.0)
            for bid in sorted(od.buy_orders, reverse=True):
                surplus = (position + bought - sold) - rotation_floor
                if surplus <= 0 or bid < rotation_trigger:
                    break
                qty = min(od.buy_orders[bid], surplus)
                if qty <= 0:
                    continue
                orders.append(Order(product, bid, -qty))
                sold += qty

        if buy_cap > 0 and od.sell_orders:
            buy_limit = fair + (1 if strong_trend else 0)
            for ask in sorted(od.sell_orders):
                if buy_cap - bought <= 0:
                    break
                if ask > buy_limit:
                    break
                qty = min(-od.sell_orders[ask], buy_cap - bought)
                if qty <= 0:
                    continue
                orders.append(Order(product, ask, qty))
                bought += qty

        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        remaining_buy = buy_cap - bought
        remaining_sell = max(0, (position + bought - sold) - target)

        if remaining_buy > 0 and best_bid is not None:
            passive_bid = min(best_bid + 1, int(math.floor(fair)))
            if best_ask is None or passive_bid < best_ask:
                orders.append(
                    Order(product, passive_bid, min(self.PEPPER_PASSIVE_SIZE, remaining_buy))
                )

        if remaining_sell > 0 and best_ask is not None:
            passive_ask = max(best_ask - 1, int(math.ceil(fair)))
            if best_bid is None or passive_ask > best_bid:
                orders.append(
                    Order(product, passive_ask, -min(self.PEPPER_PASSIVE_SIZE, remaining_sell))
                )

        return orders

    def _trade_osmium(self, state: TradingState, data: Dict[str, Any]) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        od = state.order_depths[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        if best_bid is None and best_ask is None:
            return orders

        top_mid = self._mid_price(od)
        top_spread = self._spread(od, default=None)

        wall_bid, wall_ask, wall_spread = self._infer_osmium_wall(od)
        if wall_bid is not None and wall_ask is not None:
            wall_fair = (wall_bid + wall_ask) / 2.0
        elif data.get("last_wall_fair") is not None:
            wall_fair = float(data["last_wall_fair"])
        elif top_mid is not None:
            wall_fair = float(top_mid)
        else:
            wall_fair = 10000.0

        data["last_wall_fair"] = wall_fair
        data["last_mid"] = top_mid

        fair = wall_fair - position * self.OSMIUM_POSITION_SKEW
        distorted = (
            top_spread is not None
            and top_spread <= self.OSMIUM_DISTORTED_SPREAD
            and (wall_spread is None or top_spread < wall_spread)
        )

        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position
        bought = 0
        sold = 0

        # Always take obvious value relative to the inferred wall fair.
        if od.sell_orders:
            for ask in sorted(od.sell_orders):
                if ask > fair - self.OSMIUM_VALUE_TAKE_THRESHOLD or buy_cap - bought <= 0:
                    break
                qty = min(-od.sell_orders[ask], buy_cap - bought)
                if qty <= 0:
                    continue
                orders.append(Order(product, ask, qty))
                bought += qty

        if od.buy_orders:
            for bid in sorted(od.buy_orders, reverse=True):
                if bid < fair + self.OSMIUM_VALUE_TAKE_THRESHOLD or sell_cap - sold <= 0:
                    break
                qty = min(od.buy_orders[bid], sell_cap - sold)
                if qty <= 0:
                    continue
                orders.append(Order(product, bid, -qty))
                sold += qty

        # When the top of book compresses unusually, fade the transient inside distortion.
        if distorted and top_mid is not None:
            if top_mid < wall_fair - 1 and od.sell_orders:
                for ask in sorted(od.sell_orders):
                    if ask > wall_fair or buy_cap - bought <= 0:
                        break
                    qty = min(-od.sell_orders[ask], buy_cap - bought)
                    if qty <= 0:
                        continue
                    orders.append(Order(product, ask, qty))
                    bought += qty
            elif top_mid > wall_fair + 1 and od.buy_orders:
                for bid in sorted(od.buy_orders, reverse=True):
                    if bid < wall_fair or sell_cap - sold <= 0:
                        break
                    qty = min(od.buy_orders[bid], sell_cap - sold)
                    if qty <= 0:
                        continue
                    orders.append(Order(product, bid, -qty))
                    sold += qty

        if best_bid is None or best_ask is None:
            return orders

        remaining_buy = buy_cap - bought
        remaining_sell = sell_cap - sold

        bid_ceiling = int(math.floor(fair - 1))
        ask_floor = int(math.ceil(fair + 1))

        if distorted and top_mid is not None:
            if top_mid < wall_fair:
                bid_ceiling = max(bid_ceiling, int(math.floor(wall_fair - 1)))
                ask_floor = max(ask_floor, int(math.ceil(wall_fair + 1)))
            elif top_mid > wall_fair:
                bid_ceiling = min(bid_ceiling, int(math.floor(wall_fair - 1)))
                ask_floor = min(ask_floor, int(math.ceil(wall_fair + 1)))

        our_bid = min(best_bid + 1, bid_ceiling)
        our_ask = max(best_ask - 1, ask_floor)

        if remaining_buy > 0 and our_bid < best_ask:
            orders.append(Order(product, our_bid, min(self.OSMIUM_PASSIVE_SIZE, remaining_buy)))
        if remaining_sell > 0 and our_ask > best_bid:
            orders.append(
                Order(product, our_ask, -min(self.OSMIUM_PASSIVE_SIZE, remaining_sell))
            )

        return orders

    def _infer_osmium_wall(
        self, od: OrderDepth
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        if not od.buy_orders or not od.sell_orders:
            return None, None, None

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        candidates: List[Tuple[int, int, int, int, int, int, int, int]] = []

        for bid_price, bid_vol in od.buy_orders.items():
            for ask_price, ask_vol_raw in od.sell_orders.items():
                if ask_price <= bid_price:
                    continue
                ask_vol = -ask_vol_raw
                spread = ask_price - bid_price
                spread_score = min(
                    abs(spread - preferred) for preferred in self.OSMIUM_PREFERRED_SPREADS
                )
                exact_preferred = 0 if spread in self.OSMIUM_PREFERRED_SPREADS else 1
                support = min(bid_vol, ask_vol)
                balance = abs(bid_vol - ask_vol)
                depth_penalty = abs(best_bid - bid_price) + abs(ask_price - best_ask)
                candidates.append(
                    (
                        exact_preferred,
                        spread_score,
                        -support,
                        balance,
                        depth_penalty,
                        bid_price,
                        ask_price,
                        spread,
                    )
                )

        if not candidates:
            return best_bid, best_ask, best_ask - best_bid

        chosen = min(candidates)
        return chosen[5], chosen[6], chosen[7]

    @staticmethod
    def _mid_price(od: OrderDepth) -> Optional[float]:
        if od.buy_orders and od.sell_orders:
            return (max(od.buy_orders) + min(od.sell_orders)) / 2.0
        if od.buy_orders:
            return float(max(od.buy_orders))
        if od.sell_orders:
            return float(min(od.sell_orders))
        return None

    @staticmethod
    def _spread(od: OrderDepth, default: Optional[float]) -> Optional[float]:
        if od.buy_orders and od.sell_orders:
            return float(min(od.sell_orders) - max(od.buy_orders))
        return default

    @staticmethod
    def _window_mean(values: List[float], window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        return sum(sample) / len(sample)

    @staticmethod
    def _avg_abs_return(values: List[float], window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        if len(sample) < 2:
            return 1.0
        returns = [abs(sample[i] - sample[i - 1]) for i in range(1, len(sample))]
        avg = sum(returns) / len(returns)
        return avg if avg > 0 else 1.0

    @staticmethod
    def _window_slope(values: List[float], window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        n = len(sample)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(sample) / n
        numerator = sum((idx - x_mean) * (sample[idx] - y_mean) for idx in range(n))
        denominator = sum((idx - x_mean) ** 2 for idx in range(n))
        return numerator / denominator if denominator else 0.0
