import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Optional


class Trader:
    """
    v12 — IPR: dynamic trend-follow with trailing stop. ACO: EMA + position skew.
    EMA empirically beats wall inference on ACO (two bot tiers with different spreads).
    """

    POSITION_LIMIT = 80
    MARKET_ACCESS_FEE = 0

    IPR = "INTARIAN_PEPPER_ROOT"
    ACO = "ASH_COATED_OSMIUM"

    # IPR — structural ratios
    IPR_HISTORY = 160
    IPR_SHORT_RATIO = 0.15          # short MA = 15% of history
    IPR_LONG_RATIO = 0.60           # long MA  = 60% of history
    IPR_SLOPE_RATIO = 0.30          # slope window = 30% of history
    IPR_BREAK_CONFIRM = 4

    # ACO — EMA fair value
    ACO_EMA_ALPHA = 0.002           # ~500-tick half-life, tracks anchor not noise
    ACO_WARMUP = 50                 # let EMA stabilize before trading
    ACO_POSITION_SKEW = 0.10        # skew fair value per unit of position

    def bid(self):
        return self.MARKET_ACCESS_FEE

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

    # =========================================================================
    # IPR — Trend-follow, buy full immediately, exit on break
    # =========================================================================

    def _trade_ipr(self, state: TradingState, memory: dict):
        product = self.IPR
        od = state.order_depths[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        mid = self._mid_price(od)
        if mid is None:
            return orders, memory

        # --- Price history ---
        prices = memory.get("ipr_prices", [])
        prices.append(mid)
        prices = prices[-self.IPR_HISTORY:]
        memory["ipr_prices"] = prices

        # --- Trailing peak ---
        peak = memory.get("ipr_peak")
        if position <= 0 or peak is None:
            peak = mid
        else:
            peak = max(float(peak), mid)
        memory["ipr_peak"] = peak

        # --- Dynamic windows from history length ---
        n = len(prices)
        short_w = max(2, int(self.IPR_HISTORY * self.IPR_SHORT_RATIO))
        long_w = max(short_w + 1, int(self.IPR_HISTORY * self.IPR_LONG_RATIO))
        slope_w = max(2, int(self.IPR_HISTORY * self.IPR_SLOPE_RATIO))

        # --- Indicators ---
        short_ma = self._window_mean(prices, short_w)
        long_ma = self._window_mean(prices, long_w)
        slope = self._window_slope(prices, slope_w)
        vol = self._avg_abs_return(prices, slope_w)
        spread = self._spread_val(od, default=vol * 2)

        # --- Trend classification (all thresholds in vol/spread units) ---
        trail_dist = vol * 6 + spread         # trail = ~6 sigma + spread
        strong = (
            short_ma >= long_ma
            and slope > 0
            and mid >= short_ma - spread / 2
        )
        broken = (
            short_ma + vol < long_ma           # short fell below long by 1 vol
            or slope < -vol / 4                # slope negative by quarter vol
            or peak - mid > trail_dist         # drawdown from peak
        )

        break_count = int(memory.get("ipr_break_count", 0))
        break_count = break_count + 1 if broken else 0
        memory["ipr_break_count"] = break_count

        # --- Position target: full from start, exit on confirmed break ---
        if break_count >= self.IPR_BREAK_CONFIRM:
            target = 0
        else:
            target = self.POSITION_LIMIT

        # --- Fair value ---
        fair = max(mid, short_ma)
        if break_count >= self.IPR_BREAK_CONFIRM:
            fair = min(mid, short_ma)

        buy_cap = max(0, target - position)
        sell_cap = max(0, position - target)
        bought = 0
        sold = 0

        # --- Sell toward target ---
        if sell_cap > 0 and od.buy_orders:
            exit_floor = fair - (0 if break_count >= self.IPR_BREAK_CONFIRM else spread / 4)
            for bid in sorted(od.buy_orders, reverse=True):
                if sold >= sell_cap:
                    break
                if break_count < self.IPR_BREAK_CONFIRM and bid < exit_floor:
                    break
                qty = min(od.buy_orders[bid], sell_cap - sold)
                if qty > 0:
                    orders.append(Order(product, bid, -qty))
                    sold += qty

        # --- Buy toward target ---
        if buy_cap > 0 and od.sell_orders:
            buy_limit = fair + (spread / 4 if strong else 0)
            for ask in sorted(od.sell_orders):
                if bought >= buy_cap or ask > buy_limit:
                    break
                qty = min(-od.sell_orders[ask], buy_cap - bought)
                if qty > 0:
                    orders.append(Order(product, ask, qty))
                    bought += qty

        # --- Passive quotes ---
        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        remaining_buy = buy_cap - bought
        remaining_sell = max(0, (position + bought - sold) - target)
        passive_size = max(1, self.POSITION_LIMIT // 4)

        if remaining_buy > 0 and best_bid is not None:
            passive_bid = min(best_bid + 1, int(math.floor(fair)))
            if best_ask is None or passive_bid < best_ask:
                orders.append(
                    Order(product, passive_bid, min(passive_size, remaining_buy))
                )

        if remaining_sell > 0 and best_ask is not None:
            passive_ask = max(best_ask - 1, int(math.ceil(fair)))
            if best_bid is None or passive_ask > best_bid:
                orders.append(
                    Order(product, passive_ask, -min(passive_size, remaining_sell))
                )

        return orders, memory

    # =========================================================================
    # ACO — Market-make around EMA fair value with position skew
    # =========================================================================

    def _trade_aco(self, state: TradingState, memory: dict):
        product = self.ACO
        od = state.order_depths[product]
        orders: List[Order] = []

        if not od.buy_orders or not od.sell_orders:
            return orders, memory

        mid = (max(od.buy_orders) + min(od.sell_orders)) / 2

        # --- EMA fair value ---
        aco_ticks = memory.get("aco_ticks", 0)
        fv = memory.get("aco_fv", mid)
        fv = (1 - self.ACO_EMA_ALPHA) * fv + self.ACO_EMA_ALPHA * mid
        aco_ticks += 1
        memory["aco_fv"] = fv
        memory["aco_ticks"] = aco_ticks

        if aco_ticks < self.ACO_WARMUP:
            return orders, memory

        # --- Position-skewed fair value ---
        position = state.position.get(product, 0)
        fair = fv - position * self.ACO_POSITION_SKEW

        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position

        # --- Take: asks below fair, bids above fair ---
        for ask in sorted(od.sell_orders):
            if ask >= fair or buy_cap <= 0:
                break
            qty = min(buy_cap, abs(od.sell_orders[ask]))
            orders.append(Order(product, ask, qty))
            buy_cap -= qty

        for bid in sorted(od.buy_orders, reverse=True):
            if bid <= fair or sell_cap <= 0:
                break
            qty = min(sell_cap, od.buy_orders[bid])
            orders.append(Order(product, bid, -qty))
            sell_cap -= qty

        # --- Make: one tick inside best, gated by fair ---
        our_bid = max(od.buy_orders) + 1
        our_ask = min(od.sell_orders) - 1

        if buy_cap > 0 and our_bid < fair:
            orders.append(Order(product, our_bid, buy_cap))
        if sell_cap > 0 and our_ask > fair:
            orders.append(Order(product, our_ask, -sell_cap))

        return orders, memory

    # =========================================================================
    # Shared helpers
    # =========================================================================

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
    def _spread_val(od: OrderDepth, default=None):
        if od.buy_orders and od.sell_orders:
            return float(min(od.sell_orders) - max(od.buy_orders))
        return default

    @staticmethod
    def _window_mean(values: list, window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        return sum(sample) / len(sample)

    @staticmethod
    def _window_slope(values: list, window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        n = len(sample)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(sample) / n
        num = sum((i - x_mean) * (sample[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0

    @staticmethod
    def _avg_abs_return(values: list, window: int) -> float:
        sample = values[-window:] if len(values) > window else values
        if len(sample) < 2:
            return 1.0
        returns = [abs(sample[i] - sample[i - 1]) for i in range(1, len(sample))]
        avg = sum(returns) / len(returns)
        return avg if avg > 0 else 1.0
