from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    POSITION_LIMIT = 80

    # Pepper parameters
    PEPPER_MA_WINDOW = 20        # ticks to compute moving average
    PEPPER_TRAIL_STOP = 30       # sell if price drops this much from peak
    PEPPER_EARLY_CUTOFF = 300000 # aggressive buying in first ~30% of day

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            result["INTARIAN_PEPPER_ROOT"] = self._trade_pepper(state, trader_data)

        return result, 0, json.dumps(trader_data)

    def _load_data(self, raw: str) -> dict:
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return {"pepper_prices": [], "pepper_peak": 0}

    # -------------------------------------------------------------------------
    # INTARIAN_PEPPER_ROOT
    #
    # Price trends up ~1000/day.  Three improvements over "buy everything":
    #   1. Early aggressive buying  – first 30% of the day
    #   2. Moving-average guard     – skip buying if mid < MA
    #   3. Trailing stop            – sell if price drops >TRAIL_STOP from peak
    # -------------------------------------------------------------------------

    def _trade_pepper(self, state: TradingState, data: dict) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        order_depth = state.order_depths[product]
        orders: List[Order] = []
        position = state.position.get(product, 0)

        mid = self._mid_price(order_depth)
        if mid is None:
            return orders

        prices = data.get("pepper_prices", [])
        prices.append(mid)
        if len(prices) > self.PEPPER_MA_WINDOW:
            prices = prices[-self.PEPPER_MA_WINDOW:]
        data["pepper_prices"] = prices

        peak = data.get("pepper_peak", 0)
        if mid > peak:
            peak = mid
        data["pepper_peak"] = peak

        ma = sum(prices) / len(prices)

        # Trailing stop: sell if price collapsed from peak
        if peak - mid > self.PEPPER_TRAIL_STOP and position > 0:
            return self._sell_pepper(order_depth, product, position)

        early_phase = state.timestamp < self.PEPPER_EARLY_CUTOFF
        trend_ok = mid >= ma

        if early_phase:
            return self._buy_pepper_aggressive(order_depth, product, position)
        elif trend_ok:
            return self._buy_pepper_conservative(order_depth, product, position)
        else:
            return orders

    def _buy_pepper_aggressive(self, od: OrderDepth, product: str, position: int) -> List[Order]:
        orders: List[Order] = []
        cap = self.POSITION_LIMIT - position

        for ask in sorted(od.sell_orders.keys()):
            if cap <= 0:
                break
            qty = min(cap, -od.sell_orders[ask])
            orders.append(Order(product, ask, qty))
            cap -= qty

        if cap > 0 and od.buy_orders:
            best_bid = max(od.buy_orders.keys())
            orders.append(Order(product, best_bid + 1, cap))

        return orders

    def _buy_pepper_conservative(self, od: OrderDepth, product: str, position: int) -> List[Order]:
        orders: List[Order] = []
        cap = self.POSITION_LIMIT - position

        for ask in sorted(od.sell_orders.keys()):
            if cap <= 0:
                break
            qty = min(cap, -od.sell_orders[ask])
            orders.append(Order(product, ask, qty))
            cap -= qty

        return orders

    def _sell_pepper(self, od: OrderDepth, product: str, position: int) -> List[Order]:
        orders: List[Order] = []
        remaining = position

        for bid in sorted(od.buy_orders.keys(), reverse=True):
            if remaining <= 0:
                break
            qty = min(remaining, od.buy_orders[bid])
            orders.append(Order(product, bid, -qty))
            remaining -= qty

        if remaining > 0 and od.sell_orders:
            best_ask = min(od.sell_orders.keys())
            orders.append(Order(product, best_ask - 1, -remaining))

        return orders

    @staticmethod
    def _mid_price(od: OrderDepth):
        if od.buy_orders and od.sell_orders:
            return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2
        if od.buy_orders:
            return max(od.buy_orders.keys())
        if od.sell_orders:
            return min(od.sell_orders.keys())
        return None
