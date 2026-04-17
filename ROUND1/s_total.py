from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    POSITION_LIMIT = 80

    # Pepper parameters
    PEPPER_MA_WINDOW = 20
    PEPPER_TRAIL_STOP = 30
    PEPPER_EARLY_CUTOFF = 300000

    # Osmium parameters - fixed fair value market-making
    FAIR_VALUE = 10000
    POSITION_SKEW = 0.15
    TAKE_THRESHOLD = 2
    TIGHT_SPREAD_THRESHOLD = 14

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        for product in state.order_depths:
            if product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state, trader_data)
            elif product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_osmium(state, trader_data)

        return result, 0, json.dumps(trader_data)

    # -------------------------------------------------------------------------
    # State persistence
    # -------------------------------------------------------------------------

    def _load_data(self, raw: str) -> dict:
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return {"pepper_prices": [], "pepper_peak": 0, "last_mid": None}

    # -------------------------------------------------------------------------
    # INTARIAN_PEPPER_ROOT
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

    # -------------------------------------------------------------------------
    # ASH_COATED_OSMIUM - Fixed fair value market-making
    # -------------------------------------------------------------------------

    def _trade_osmium(self, state: TradingState, data: dict) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        od = state.order_depths[product]
        orders: List[Order] = []
        position = state.position.get(product, 0)
        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position

        if not od.sell_orders and not od.buy_orders:
            return orders

        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else (best_bid or best_ask)

        last_mid = data.get("last_mid")
        data["last_mid"] = mid

        fair = self.FAIR_VALUE - position * self.POSITION_SKEW

        spread = (best_ask - best_bid) if (best_ask and best_bid) else 999
        tight_spread = spread < self.TIGHT_SPREAD_THRESHOLD

        last_delta = (mid - last_mid) if last_mid is not None else 0

        # LAYER 1: Take mispriced NPC levels
        take_fair = fair - self.TAKE_THRESHOLD if not tight_spread else fair
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price >= take_fair or buy_cap <= 0:
                break
            qty = min(buy_cap, -od.sell_orders[ask_price])
            orders.append(Order(product, ask_price, qty))
            buy_cap -= qty

        take_fair_sell = fair + self.TAKE_THRESHOLD if not tight_spread else fair
        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price <= take_fair_sell or sell_cap <= 0:
                break
            qty = min(sell_cap, od.buy_orders[bid_price])
            orders.append(Order(product, bid_price, -qty))
            sell_cap -= qty

        # LAYER 2: During tight spread, trade into the mean-reversion
        if tight_spread and best_bid and best_ask:
            if mid < self.FAIR_VALUE - 2 and buy_cap > 0:
                for ask_price in sorted(od.sell_orders.keys()):
                    if buy_cap <= 0 or ask_price > self.FAIR_VALUE:
                        break
                    qty = min(buy_cap, -od.sell_orders[ask_price])
                    orders.append(Order(product, ask_price, qty))
                    buy_cap -= qty

            elif mid > self.FAIR_VALUE + 2 and sell_cap > 0:
                for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                    if sell_cap <= 0 or bid_price < self.FAIR_VALUE:
                        break
                    qty = min(sell_cap, od.buy_orders[bid_price])
                    orders.append(Order(product, bid_price, -qty))
                    sell_cap -= qty

        # LAYER 3: Post resting quotes inside the spread
        if best_bid and best_ask:
            our_bid = best_bid + 1
            our_ask = best_ask - 1

            if last_delta > 0:
                our_ask = max(our_ask - 1, int(fair) + 1)
            elif last_delta < 0:
                our_bid = min(our_bid + 1, int(fair) - 1)

            if our_bid < fair and buy_cap > 0:
                orders.append(Order(product, our_bid, buy_cap))
            if our_ask > fair and sell_cap > 0:
                orders.append(Order(product, our_ask, -sell_cap))

        return orders

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _mid_price(od: OrderDepth):
        if od.buy_orders and od.sell_orders:
            return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2
        if od.buy_orders:
            return max(od.buy_orders.keys())
        if od.sell_orders:
            return min(od.sell_orders.keys())
        return None
