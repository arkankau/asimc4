from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "imc_backtester"))


def load_core():
    spec = importlib.util.spec_from_file_location("vev_trader_core", ROOT / "vev_trader_core.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VevStrategyModeTests(unittest.TestCase):
    def test_core_exposes_strategy_modes(self) -> None:
        core = load_core()
        self.assertTrue(hasattr(core.BaseVevTrader, "STRATEGY_MODE"))
        self.assertEqual(core.BaseVevTrader.STRATEGY_MODE, "smile")

    def test_core_trade_pairs_exclude_dead_strikes(self) -> None:
        core = load_core()
        pairs = core.BaseVevTrader()._trade_pairs()
        self.assertIn(("VEV_5200", "VEV_5300"), pairs)
        self.assertTrue(all("VEV_6000" not in pair and "VEV_6500" not in pair for pair in pairs))

    def test_zscore_mode_uses_recent_mid_history_only(self) -> None:
        core = load_core()
        trader = core.BaseVevTrader()
        trader.STRATEGY_MODE = "zscore"

        history = [100.0] * 24 + [106.0]
        target = trader._zscore_target_from_history(
            voucher="VEV_5300",
            price_history=history,
            current_mid=106.0,
            spread=2.0,
            tte_years=5.0 / 252.0,
            late_session=False,
        )

        self.assertLess(target, 0)


if __name__ == "__main__":
    unittest.main()
