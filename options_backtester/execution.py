from __future__ import annotations

import math
from dataclasses import dataclass, field

from imc_backtester.datamodel import Order, Trade
from imc_backtester.log_parser import PriceSnapshot, TapeTrade


@dataclass
class WorkingOrder:
    symbol: str
    price: int
    remaining_quantity: int
    queue_ahead: int
    created_timestamp: int


@dataclass(frozen=True)
class FillEvent:
    symbol: str
    side: str
    price: int
    quantity: int
    reason: str
    timestamp: int


@dataclass(frozen=True)
class ReconcileResult:
    aggressive_fills: list[Trade]
    fill_events: list[FillEvent]
    resting_summary: dict[str, list[WorkingOrder]]


@dataclass(frozen=True)
class ProcessResult:
    own_trades: dict[str, list[Trade]]
    market_trades: dict[str, list[Trade]]
    fill_events: list[FillEvent]


@dataclass(frozen=True)
class ExecutionAssumptions:
    queue_ahead_ratio: float


MODE_ASSUMPTIONS = {
    "conservative": ExecutionAssumptions(queue_ahead_ratio=0.75),
    "balanced": ExecutionAssumptions(queue_ahead_ratio=0.5),
    "optimistic": ExecutionAssumptions(queue_ahead_ratio=0.25),
}


def _best_bid(snapshot: PriceSnapshot) -> tuple[int | None, int]:
    if snapshot.bid_prices:
        return snapshot.bid_prices[0], snapshot.bid_volumes[0]
    return None, 0


def _best_ask(snapshot: PriceSnapshot) -> tuple[int | None, int]:
    if snapshot.ask_prices:
        return snapshot.ask_prices[0], snapshot.ask_volumes[0]
    return None, 0


def _trade_to_market(trade: TapeTrade, timestamp: int) -> Trade:
    return Trade(
        symbol=trade.symbol,
        price=trade.price,
        quantity=trade.quantity,
        buyer=trade.buyer,
        seller=trade.seller,
        timestamp=timestamp,
    )


def _fill_trade(symbol: str, price: int, quantity: int, is_buy: bool, timestamp: int) -> Trade:
    return Trade(
        symbol=symbol,
        price=price,
        quantity=quantity,
        buyer="SUBMISSION" if is_buy else "",
        seller="" if is_buy else "SUBMISSION",
        timestamp=timestamp,
    )


class PersistentExecutionEngine:
    def __init__(self, mode: str = "conservative") -> None:
        if mode not in MODE_ASSUMPTIONS:
            raise ValueError(f"Unsupported execution mode: {mode}")
        self.mode = mode
        self.assumptions = MODE_ASSUMPTIONS[mode]
        self._working_orders: dict[str, list[WorkingOrder]] = {}

    def snapshot(self) -> dict[str, list[WorkingOrder]]:
        return {symbol: [WorkingOrder(**vars(order)) for order in orders] for symbol, orders in self._working_orders.items()}

    def reconcile_target_orders(
        self,
        *,
        desired_orders: dict[str, list[Order]],
        snapshots: dict[str, PriceSnapshot],
        timestamp: int,
    ) -> ReconcileResult:
        aggressive_fills: list[Trade] = []
        fill_events: list[FillEvent] = []
        next_orders: dict[str, list[WorkingOrder]] = {}

        for symbol in set(self._working_orders) | set(desired_orders):
            snapshot = snapshots.get(symbol)
            existing_by_key = {
                (order.price, 1 if order.remaining_quantity > 0 else -1): order
                for order in self._working_orders.get(symbol, [])
            }
            current_orders: list[WorkingOrder] = []
            best_bid, bid_volume = _best_bid(snapshot) if snapshot is not None else (None, 0)
            best_ask, ask_volume = _best_ask(snapshot) if snapshot is not None else (None, 0)
            available_bid = bid_volume
            available_ask = ask_volume

            for desired in desired_orders.get(symbol, []):
                remaining_quantity = desired.quantity
                is_buy = remaining_quantity > 0
                if snapshot is not None and is_buy and best_ask is not None and desired.price >= best_ask and available_ask > 0:
                    filled = min(remaining_quantity, available_ask)
                    if filled > 0:
                        aggressive_fills.append(_fill_trade(symbol, best_ask, filled, True, timestamp))
                        fill_events.append(FillEvent(symbol, "buy", best_ask, filled, "aggressive_visible", timestamp))
                        remaining_quantity -= filled
                        available_ask -= filled
                elif snapshot is not None and not is_buy and best_bid is not None and desired.price <= best_bid and available_bid > 0:
                    filled = min(-remaining_quantity, available_bid)
                    if filled > 0:
                        aggressive_fills.append(_fill_trade(symbol, best_bid, filled, False, timestamp))
                        fill_events.append(FillEvent(symbol, "sell", best_bid, filled, "aggressive_visible", timestamp))
                        remaining_quantity += filled
                        available_bid -= filled

                if remaining_quantity == 0:
                    continue

                side = 1 if remaining_quantity > 0 else -1
                key = (desired.price, side)
                carried = existing_by_key.get(key)
                if carried is not None:
                    target_abs = abs(remaining_quantity)
                    current_abs = abs(carried.remaining_quantity)
                    if target_abs > current_abs:
                        carried.queue_ahead += target_abs - current_abs
                    carried.remaining_quantity = side * target_abs
                    current_orders.append(carried)
                    continue

                current_orders.append(
                    WorkingOrder(
                        symbol=symbol,
                        price=desired.price,
                        remaining_quantity=remaining_quantity,
                        queue_ahead=self._initial_queue_ahead(snapshot, desired.price, remaining_quantity),
                        created_timestamp=timestamp,
                    )
                )

            if current_orders:
                next_orders[symbol] = current_orders

        self._working_orders = next_orders
        return ReconcileResult(
            aggressive_fills=aggressive_fills,
            fill_events=fill_events,
            resting_summary=self.snapshot(),
        )

    def process_resting_orders(
        self,
        *,
        snapshots: dict[str, PriceSnapshot],
        tape_trades: dict[str, list[TapeTrade]],
        timestamp: int,
    ) -> ProcessResult:
        own_trades: dict[str, list[Trade]] = {}
        market_trades: dict[str, list[Trade]] = {}
        fill_events: list[FillEvent] = []
        next_orders: dict[str, list[WorkingOrder]] = {}

        for symbol, orders in self._working_orders.items():
            snapshot = snapshots.get(symbol)
            trades = tape_trades.get(symbol, [])
            if trades:
                market_trades[symbol] = [_trade_to_market(trade, timestamp) for trade in trades]
            if snapshot is None:
                next_orders[symbol] = orders
                continue

            best_bid, bid_volume = _best_bid(snapshot)
            best_ask, ask_volume = _best_ask(snapshot)
            available_bid = bid_volume
            available_ask = ask_volume
            mid_price = snapshot.mid_price
            remaining_orders: list[WorkingOrder] = []

            seller_touch_volume = sum(trade.quantity for trade in trades if trade.price <= (best_bid or trade.price) and trade.price < mid_price)
            buyer_touch_volume = sum(trade.quantity for trade in trades if trade.price >= (best_ask or trade.price) and trade.price > mid_price)

            for order in orders:
                if order.remaining_quantity > 0:
                    if best_ask is not None and best_ask <= order.price and available_ask > 0:
                        filled = min(order.remaining_quantity, available_ask)
                        own_trades.setdefault(symbol, []).append(_fill_trade(symbol, best_ask, filled, True, timestamp))
                        fill_events.append(FillEvent(symbol, "buy", best_ask, filled, "book_cross", timestamp))
                        available_ask -= filled
                        order.remaining_quantity -= filled
                    elif seller_touch_volume > 0:
                        if seller_touch_volume <= order.queue_ahead:
                            order.queue_ahead -= seller_touch_volume
                        else:
                            remaining_flow = seller_touch_volume - order.queue_ahead
                            order.queue_ahead = 0
                            filled = min(order.remaining_quantity, remaining_flow)
                            if filled > 0:
                                own_trades.setdefault(symbol, []).append(_fill_trade(symbol, order.price, filled, True, timestamp))
                                fill_events.append(FillEvent(symbol, "buy", order.price, filled, "touch_and_consume", timestamp))
                                order.remaining_quantity -= filled
                else:
                    sell_qty = -order.remaining_quantity
                    if best_bid is not None and best_bid >= order.price and available_bid > 0:
                        filled = min(sell_qty, available_bid)
                        own_trades.setdefault(symbol, []).append(_fill_trade(symbol, best_bid, filled, False, timestamp))
                        fill_events.append(FillEvent(symbol, "sell", best_bid, filled, "book_cross", timestamp))
                        available_bid -= filled
                        order.remaining_quantity += filled
                    elif buyer_touch_volume > 0:
                        if buyer_touch_volume <= order.queue_ahead:
                            order.queue_ahead -= buyer_touch_volume
                        else:
                            remaining_flow = buyer_touch_volume - order.queue_ahead
                            order.queue_ahead = 0
                            filled = min(sell_qty, remaining_flow)
                            if filled > 0:
                                own_trades.setdefault(symbol, []).append(_fill_trade(symbol, order.price, filled, False, timestamp))
                                fill_events.append(FillEvent(symbol, "sell", order.price, filled, "touch_and_consume", timestamp))
                                order.remaining_quantity += filled

                if order.remaining_quantity != 0:
                    remaining_orders.append(order)

            if remaining_orders:
                next_orders[symbol] = remaining_orders

        self._working_orders = next_orders
        return ProcessResult(own_trades=own_trades, market_trades=market_trades, fill_events=fill_events)

    def _initial_queue_ahead(self, snapshot: PriceSnapshot | None, price: int, quantity: int) -> int:
        if snapshot is None:
            return 0
        best_bid, bid_volume = _best_bid(snapshot)
        best_ask, ask_volume = _best_ask(snapshot)
        if quantity > 0 and best_bid is not None and price == best_bid:
            return int(math.ceil(self.assumptions.queue_ahead_ratio * bid_volume))
        if quantity < 0 and best_ask is not None and price == best_ask:
            return int(math.ceil(self.assumptions.queue_ahead_ratio * ask_volume))
        return 0
