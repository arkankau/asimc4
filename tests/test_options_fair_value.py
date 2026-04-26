from __future__ import annotations

import unittest

from imc_backtester.log_parser import PriceSnapshot

from options_backtester.fair_value import UNDERLYING, build_fair_value_snapshot


def _snapshot(
    product: str,
    *,
    bid: int,
    ask: int,
    mid: float | None = None,
    bid_volume: int = 20,
    ask_volume: int = 20,
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


class FairValueSnapshotTests(unittest.TestCase):
    def test_build_fair_value_snapshot_exposes_signal_inventory_and_liquidation_marks(self) -> None:
        snapshots = {
            UNDERLYING: _snapshot(UNDERLYING, bid=5249, ask=5251, mid=5250.0),
            "VEV_5000": _snapshot("VEV_5000", bid=265, ask=267, mid=266.0),
            "VEV_5200": _snapshot("VEV_5200", bid=100, ask=102, mid=101.0),
            "VEV_5300": _snapshot("VEV_5300", bid=49, ask=51, mid=50.0),
            "VEV_5400": _snapshot("VEV_5400", bid=15, ask=17, mid=16.0),
            "VEV_6500": _snapshot("VEV_6500", bid=0, ask=1, mid=0.5),
        }

        valuation = build_fair_value_snapshot(
            snapshots=snapshots,
            previous_marks={product: snapshot.mid_price for product, snapshot in snapshots.items()},
            positions={"VEV_5300": 7, "VEV_5400": -4},
            expiry_days_at_start=8.0,
            global_timestamp=0,
        )

        self.assertGreater(valuation.signal_marks["VEV_5300"], 0.0)
        self.assertEqual(valuation.inventory_marks["VEV_5300"], 49.0)
        self.assertEqual(valuation.inventory_marks["VEV_5400"], 17.0)
        self.assertLessEqual(valuation.liquidation_marks["VEV_5300"], valuation.signal_marks["VEV_5300"])
        self.assertGreaterEqual(valuation.liquidation_marks["VEV_5400"], valuation.signal_marks["VEV_5400"])

        near_atm = valuation.diagnostics["VEV_5300"]
        deep_otm = valuation.diagnostics["VEV_6500"]
        self.assertIs(near_atm.used_in_fit, True)
        self.assertIs(deep_otm.used_in_fit, False)
        self.assertIsNotNone(near_atm.fitted_iv)
        self.assertIsNotNone(near_atm.delta)
        self.assertIsNotNone(near_atm.vega)
        self.assertIsNotNone(near_atm.theta)
        self.assertIsNotNone(near_atm.price_residual)

    def test_build_fair_value_snapshot_flags_vertical_spread_violations(self) -> None:
        snapshots = {
            UNDERLYING: _snapshot(UNDERLYING, bid=5249, ask=5251, mid=5250.0),
            "VEV_5200": _snapshot("VEV_5200", bid=150, ask=152, mid=151.0),
            "VEV_5300": _snapshot("VEV_5300", bid=10, ask=12, mid=11.0),
            "VEV_5400": _snapshot("VEV_5400", bid=9, ask=11, mid=10.0),
        }

        valuation = build_fair_value_snapshot(
            snapshots=snapshots,
            previous_marks={product: snapshot.mid_price for product, snapshot in snapshots.items()},
            positions={},
            expiry_days_at_start=8.0,
            global_timestamp=0,
        )

        diag = valuation.diagnostics["VEV_5300"]
        self.assertIn("vertical_spread_monotonicity", diag.repair_flags)


if __name__ == "__main__":
    unittest.main()
