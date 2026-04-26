from __future__ import annotations

import runpy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildVevVariantsTests(unittest.TestCase):
    def test_build_variants_generates_three_standalone_traders(self) -> None:
        runpy.run_path(str(ROOT / "build_vev_variants.py"), run_name="__main__")

        for name in ("vev_trader_zscore.py", "vev_trader_bs.py", "vev_trader_smile.py"):
            path = ROOT / name
            self.assertTrue(path.exists(), f"missing generated file: {name}")
            text = path.read_text()
            self.assertIn("class Trader(BaseVevTrader):", text)
            self.assertIn("from datamodel import Order, OrderDepth, TradingState", text)
            self.assertNotIn("from vev_trader_core", text)


if __name__ == "__main__":
    unittest.main()
