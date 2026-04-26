from __future__ import annotations

import unittest

from imc_backtester.datamodel import Order
from imc_backtester.log_parser import PriceSnapshot, TapeTrade

from options_backtester.execution import PersistentExecutionEngine


def _snapshot(
    product: str,
    *,
    bid: int,
    ask: int,
    mid: float | None = None,
    bid_volume: int = 10,
    ask_volume: int = 10,
    day: int = 0,
    timestamp: int = 0,
) -> PriceSnapshot:
    return PriceSnapshot(
        day=day,
        timestamp=timestamp,
        product=product,
        bid_prices=[bid],
        bid_volumes=[bid_volume],
        ask_prices=[ask],
        ask_volumes=[ask_volume],
        mid_price=float(mid if mid is not None else 0.5 * (bid + ask)),
    )


class PersistentExecutionEngineTests(unittest.TestCase):
    def test_new_passive_order_rests_without_same_tick_fill(self) -> None:
        engine = PersistentExecutionEngine(mode="conservative")
        snapshots = {"VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0, bid_volume=12)}

        resting = engine.reconcile_target_orders(
            desired_orders={"VEV_5300": [Order("VEV_5300", 49, 5)]},
            snapshots=snapshots,
            timestamp=0,
        )

        self.assertEqual(resting.aggressive_fills, [])
        self.assertEqual(resting.resting_summary["VEV_5300"][0].price, 49)
        self.assertEqual(resting.resting_summary["VEV_5300"][0].remaining_quantity, 5)

    def test_resting_order_fills_later_when_book_trades_through_price(self) -> None:
        engine = PersistentExecutionEngine(mode="conservative")
        start = {"VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0, bid_volume=12)}
        engine.reconcile_target_orders(
            desired_orders={"VEV_5300": [Order("VEV_5300", 49, 5)]},
            snapshots=start,
            timestamp=0,
        )

        later = {"VEV_5300": _snapshot("VEV_5300", bid=48, ask=49, mid=48.5, bid_volume=6, ask_volume=5, timestamp=100)}
        processed = engine.process_resting_orders(
            snapshots=later,
            tape_trades={"VEV_5300": []},
            timestamp=100,
        )

        self.assertEqual(len(processed.own_trades["VEV_5300"]), 1)
        self.assertEqual(processed.fill_events[0].reason, "book_cross")
        self.assertEqual(processed.own_trades["VEV_5300"][0].quantity, 5)

    def test_queue_ahead_requires_multiple_touch_events_before_fill(self) -> None:
        engine = PersistentExecutionEngine(mode="conservative")
        start = {"VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0, bid_volume=10)}
        engine.reconcile_target_orders(
            desired_orders={"VEV_5300": [Order("VEV_5300", 49, 5)]},
            snapshots=start,
            timestamp=0,
        )

        first_touch = engine.process_resting_orders(
            snapshots={"VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0, bid_volume=10, timestamp=100)},
            tape_trades={
                "VEV_5300": [
                    TapeTrade(timestamp=100, buyer="", seller="MM", symbol="VEV_5300", currency="XIRECS", price=49, quantity=4)
                ]
            },
            timestamp=100,
        )
        second_touch = engine.process_resting_orders(
            snapshots={"VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0, bid_volume=10, timestamp=200)},
            tape_trades={
                "VEV_5300": [
                    TapeTrade(timestamp=200, buyer="", seller="MM", symbol="VEV_5300", currency="XIRECS", price=49, quantity=12)
                ]
            },
            timestamp=200,
        )

        self.assertEqual(first_touch.own_trades, {})
        self.assertEqual(len(second_touch.own_trades["VEV_5300"]), 1)
        self.assertEqual(second_touch.fill_events[0].reason, "touch_and_consume")


if __name__ == "__main__":
    unittest.main()
