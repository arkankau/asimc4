from datamodel import OrderDepth, Order, TradingState
from typing import Any, Dict, List, Optional
import json
import math


class Trader:
    POSITION_LIMIT = 80
    PEPPER_HISTORY = 160
    PEPPER_SHORT_WINDOW = 24
    PEPPER_LONG_WINDOW = 96
    PEPPER_SLOPE_WINDOW = 48
    PEPPER_WEAK_CONFIRM = 6
    PEPPER_BREAK_CONFIRM = 4
    PEPPER_CORE_TARGET = POSITION_LIMIT // 2
    PEPPER_WARMUP_TARGET = 60
    PEPPER_PASSIVE_SIZE = 20

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self._trade_pepper(state, trader_data)

        return result, 0, json.dumps(trader_data)

    def _load_data(self, raw: str) -> Dict[str, Any]:
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    prices = parsed.get("prices", parsed.get("pepper_prices", []))
                    if not isinstance(prices, list):
                        prices = []
                    return {
                        "prices": prices[-self.PEPPER_HISTORY :],
                        "peak": parsed.get("peak", parsed.get("pepper_peak")),
                        "weak_count": int(parsed.get("weak_count", parsed.get("pepper_weak_count", 0)) or 0),
                        "break_count": int(parsed.get("break_count", parsed.get("pepper_break_count", 0)) or 0),
                    }
            except (json.JSONDecodeError, TypeError):
                pass

        return {"prices": [], "peak": None, "weak_count": 0, "break_count": 0}

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
                if buy_cap - bought <= 0 or ask > buy_limit:
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
    def _spread(od: OrderDepth, default: float) -> float:
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
