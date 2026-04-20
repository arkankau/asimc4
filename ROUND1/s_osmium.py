from datamodel import OrderDepth, Order, TradingState
from typing import Any, Dict, List, Optional, Tuple
import json
import math


class Trader:
    POSITION_LIMIT = 80
    OSMIUM_POSITION_SKEW = 0.10
    OSMIUM_VALUE_TAKE_THRESHOLD = 2
    OSMIUM_DISTORTED_SPREAD = 13
    OSMIUM_PASSIVE_SIZE = 20
    OSMIUM_PREFERRED_SPREADS = (16, 18, 19, 21)

    def run(self, state: TradingState):
        result = {}
        trader_data = self._load_data(state.traderData)

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(state, trader_data)

        return result, 0, json.dumps(trader_data)

    def _load_data(self, raw: str) -> Dict[str, Any]:
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return {
                        "last_mid": parsed.get("last_mid"),
                        "last_wall_fair": parsed.get("last_wall_fair"),
                    }
            except (json.JSONDecodeError, TypeError):
                pass
        return {"last_mid": None, "last_wall_fair": None}

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
            orders.append(
                Order(product, our_bid, min(self.OSMIUM_PASSIVE_SIZE, remaining_buy))
            )
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
