# VEV Round 3 Multi-Trader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three standalone, directly submittable Round 3 VEV trader files (`vev_trader_zscore.py`, `vev_trader_bs.py`, `vev_trader_smile.py`), compare them on the repo's Round 3 data, and promote the strongest live bot to `vev_trader.py`.

**Architecture:** Keep the existing `vev_trader_core.py` as the shared internal source of option math, book handling, risk controls, and execution utilities, then extend the variant generator so it can emit self-contained submission files for three different signal families. Add focused tests around generated file shape and strategy-specific behavior, then run the Round 3 options backtester across all three strategies to select the live default.

**Tech Stack:** Python 3, IMC `datamodel`, existing `imc_backtester` CLI, `pytest`, git.

---

## File Structure

- Modify: `build_vev_variants.py`
  - Expand variant generation from the current smile-family variants into three standalone strategy families plus the promoted default.
- Modify: `vev_trader_core.py`
  - Generalize the core so it can support z-score, single-vol Black-Scholes, and smile-residual strategies without local imports in final generated outputs.
- Modify: `vev_trader.py`
  - Keep this as the promoted best live standalone trader after backtest comparison.
- Create: `vev_trader_zscore.py`
  - Standalone submission file for per-voucher time-series mean reversion.
- Create: `vev_trader_bs.py`
  - Standalone submission file for single-vol Black-Scholes pricing.
- Create: `vev_trader_smile.py`
  - Standalone submission file for smile-fit residual scalping.
- Create: `tests/test_build_vev_variants.py`
  - Verifies variant generation produces standalone files with the expected class names and strategy flags.
- Create: `tests/test_vev_strategy_modes.py`
  - Verifies strategy-specific target-generation behavior on controlled snapshots.
- Create: `vev_trader_comparison.md`
  - Short comparison note capturing the backtest ranking and the promoted live default.

### Task 1: Add Variant-Generation Coverage

**Files:**
- Create: `tests/test_build_vev_variants.py`
- Modify: `build_vev_variants.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]


def test_build_variants_generates_three_standalone_traders():
    target_files = [
        ROOT / "vev_trader_zscore.py",
        ROOT / "vev_trader_bs.py",
        ROOT / "vev_trader_smile.py",
    ]

    for path in target_files:
        if path.exists():
            path.unlink()

    runpy.run_path(str(ROOT / "build_vev_variants.py"), run_name="__main__")

    for path in target_files:
        assert path.exists(), f"missing generated file: {path.name}"
        text = path.read_text()
        assert "class Trader(BaseVevTrader):" in text
        assert "from datamodel import Order, OrderDepth, TradingState" in text
        assert "from vev_trader_core" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_build_vev_variants.py -q
```

Expected: FAIL because the generator does not yet create `vev_trader_zscore.py`, `vev_trader_bs.py`, and `vev_trader_smile.py`.

- [ ] **Step 3: Write minimal implementation**

Update `build_vev_variants.py` so `VARIANTS` includes:

```python
VARIANTS = {
    "vev_trader_zscore.py": [
        'class Trader(BaseVevTrader):',
        '    VARIANT_NAME = "zscore_core"',
        '    STRATEGY_MODE = "zscore"',
    ],
    "vev_trader_bs.py": [
        'class Trader(BaseVevTrader):',
        '    VARIANT_NAME = "black_scholes_single_vol"',
        '    STRATEGY_MODE = "black_scholes"',
        '    ENABLE_VERTICAL_ARB = True',
    ],
    "vev_trader_smile.py": [
        'class Trader(BaseVevTrader):',
        '    VARIANT_NAME = "smile_residual_live"',
        '    STRATEGY_MODE = "smile"',
        '    USE_NORMALIZED_RESIDUAL_SCORE = True',
        '    USE_COMPRESSION_TRIGGER = True',
        '    USE_DYNAMIC_STRIKE_ACTIVATION = True',
        '    DYNAMIC_ACTIVATION_VEGA_MIN = 2.5',
        '    DYNAMIC_REVERSION_MIN_OBS = 6',
        '    DYNAMIC_REVERSION_HIT_RATE_MIN = 0.5',
    ],
    "vev_trader.py": [
        'class Trader(BaseVevTrader):',
        '    VARIANT_NAME = "smile_residual_live"',
        '    STRATEGY_MODE = "smile"',
        '    USE_NORMALIZED_RESIDUAL_SCORE = True',
        '    USE_COMPRESSION_TRIGGER = True',
        '    USE_DYNAMIC_STRIKE_ACTIVATION = True',
        '    DYNAMIC_ACTIVATION_VEGA_MIN = 2.5',
        '    DYNAMIC_REVERSION_MIN_OBS = 6',
        '    DYNAMIC_REVERSION_HIT_RATE_MIN = 0.5',
    ],
}
```

Keep the generator writing the shared `vev_trader_core.py` source plus the strategy-specific `Trader` subclass into each output file so every generated file remains directly submittable.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_build_vev_variants.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add build_vev_variants.py tests/test_build_vev_variants.py
git commit -m "test: cover standalone VEV variant generation"
```

### Task 2: Add Strategy-Mode Plumbing To The Core

**Files:**
- Create: `tests/test_vev_strategy_modes.py`
- Modify: `vev_trader_core.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "imc_backtester"))


def load_core():
    spec = importlib.util.spec_from_file_location("vev_trader_core", ROOT / "vev_trader_core.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_core_exposes_strategy_modes():
    core = load_core()
    assert hasattr(core.BaseVevTrader, "STRATEGY_MODE")
    assert core.BaseVevTrader.STRATEGY_MODE == "smile"


def test_core_trade_pairs_exclude_dead_strikes():
    core = load_core()
    pairs = core.BaseVevTrader()._trade_pairs()
    assert ("VEV_5200", "VEV_5300") in pairs
    assert all("VEV_6000" not in pair and "VEV_6500" not in pair for pair in pairs)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
```

Expected: FAIL because `STRATEGY_MODE` is not yet defined and the trade-pair filtering is not strategy-aware.

- [ ] **Step 3: Write minimal implementation**

Add these definitions to `BaseVevTrader` in `vev_trader_core.py`:

```python
    STRATEGY_MODE = "smile"
    ZSCORE_ONLY_VOUCHERS = CORE_TRADE_VOUCHERS + EXPANSION_TRADE_VOUCHERS
    BS_TRADE_VOUCHERS = CORE_TRADE_VOUCHERS + EXPANSION_TRADE_VOUCHERS
```

Refine `_trade_pairs()` so it returns only adjacent pairs drawn from `SIGNAL_VOUCHERS`, which excludes the dead `VEV_6000` and `VEV_6500` strikes.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add vev_trader_core.py tests/test_vev_strategy_modes.py
git commit -m "feat: add VEV strategy mode plumbing"
```

### Task 3: Implement Z-Score Voucher Trading

**Files:**
- Modify: `vev_trader_core.py`
- Modify: `build_vev_variants.py`
- Test: `tests/test_vev_strategy_modes.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_vev_strategy_modes.py`:

```python
def test_zscore_mode_uses_recent_mid_history_only():
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

    assert target < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
```

Expected: FAIL because `_zscore_target_from_history` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `vev_trader_core.py`:

- extend `traderData` loading/saving with per-voucher `mid_history`
- append current mids for `VEV_5200`, `VEV_5300`, `VEV_5400`, `VEV_5100`, and `VEV_5500`
- add:

```python
    def _zscore_target_from_history(
        self,
        voucher: str,
        price_history: List[float],
        current_mid: float,
        spread: float,
        tte_years: float,
        late_session: bool,
    ) -> int:
        if len(price_history) < 24:
            return 0
        mean = self._mean(price_history[-24:])
        std = self._std(price_history[-24:])
        if std <= 1e-6:
            return 0
        zscore = (current_mid - mean) / std
        threshold = 1.25 if not late_session else 1.5
        if abs(zscore) < threshold:
            return 0
        base = self.VOUCHER_TRADE_UNIT * (1 + int(max(0.0, abs(zscore) - threshold)))
        scaled = int(base * self.VOUCHER_SIZE_MULTIPLIER.get(voucher, 1.0))
        rounded = max(self.VOUCHER_TRADE_UNIT, scaled // self.VOUCHER_TRADE_UNIT * self.VOUCHER_TRADE_UNIT)
        max_target = self._scaled_voucher_limit(tte_years, late_session)
        return -self._sign(zscore) * min(rounded, max_target)
```

- route `_single_voucher_target()` to that z-score helper when `STRATEGY_MODE == "zscore"`
- pass `snap["tte_years"]` into that helper from `_single_voucher_target()`

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
python3 build_vev_variants.py
python3 -m py_compile vev_trader_zscore.py
```

Expected: tests PASS and the standalone file regenerates without syntax errors.

- [ ] **Step 5: Commit**

```bash
git add vev_trader_core.py build_vev_variants.py tests/test_vev_strategy_modes.py vev_trader_zscore.py
git commit -m "feat: add standalone VEV z-score trader"
```

### Task 4: Implement Single-Vol Black-Scholes Trading

**Files:**
- Modify: `vev_trader_core.py`
- Modify: `build_vev_variants.py`
- Test: `tests/test_vev_strategy_modes.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_vev_strategy_modes.py`:

```python
def test_black_scholes_mode_returns_short_target_when_mid_is_rich():
    core = load_core()
    trader = core.BaseVevTrader()
    trader.STRATEGY_MODE = "black_scholes"

    snap = {
        "mid": 150.0,
        "fair": 143.0,
        "spread": 3.0,
        "tte_years": 5.0 / 252.0,
    }
    target = trader._bs_single_vol_target("VEV_5300", snap, late_session=False)
    assert target < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
```

Expected: FAIL because `_bs_single_vol_target` does not exist.

- [ ] **Step 3: Write minimal implementation**

In `vev_trader_core.py`:

- add `single_vol_history` to `traderData`
- derive a shared live vol estimate from the liquid middle strikes:

```python
    def _shared_live_vol(self, smile: Dict[str, Dict[str, float]]) -> Optional[float]:
        values = [
            smile[voucher]["iv"]
            for voucher in self.CORE_TRADE_VOUCHERS
            if voucher in smile and smile[voucher]["vega"] >= self.VEGA_FLOOR
        ]
        if len(values) < 2:
            return None
        return self._mean(values)
```

- for `STRATEGY_MODE == "black_scholes"`, overwrite each traded voucher's `fair` using that single shared vol
- add:

```python
    def _bs_single_vol_target(
        self, voucher: str, snap: Dict[str, float], late_session: bool
    ) -> int:
        residual = snap["mid"] - snap["fair"]
        spread = snap["spread"]
        threshold = max(1.2, 0.55 * spread)
        if abs(residual) < threshold:
            return 0
        base = self.VOUCHER_TRADE_UNIT * (1 + int(max(0.0, abs(residual) - threshold) / max(1.0, spread)))
        if late_session:
            base = max(self.VOUCHER_TRADE_UNIT, base // 2)
        scaled = int(base * self.VOUCHER_SIZE_MULTIPLIER.get(voucher, 1.0))
        rounded = max(self.VOUCHER_TRADE_UNIT, scaled // self.VOUCHER_TRADE_UNIT * self.VOUCHER_TRADE_UNIT)
        return -self._sign(residual) * min(rounded, self.VOUCHER_MAX_TARGET)
```

- route `_single_voucher_target()` to `_bs_single_vol_target()` when `STRATEGY_MODE == "black_scholes"`

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
python3 build_vev_variants.py
python3 -m py_compile vev_trader_bs.py
```

Expected: tests PASS and the standalone file regenerates without syntax errors.

- [ ] **Step 5: Commit**

```bash
git add vev_trader_core.py build_vev_variants.py tests/test_vev_strategy_modes.py vev_trader_bs.py
git commit -m "feat: add standalone VEV Black-Scholes trader"
```

### Task 5: Promote Smile Trader To Explicit Live Mode

**Files:**
- Modify: `vev_trader_core.py`
- Modify: `build_vev_variants.py`
- Test: `tests/test_vev_strategy_modes.py`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_vev_strategy_modes.py`:

```python
def test_smile_mode_still_uses_normalized_residual_logic():
    core = load_core()
    trader = core.BaseVevTrader()
    trader.STRATEGY_MODE = "smile"
    trader.USE_NORMALIZED_RESIDUAL_SCORE = True

    snap = {
        "residual": 4.0,
        "residual_score": 2.2,
        "spread": 2.0,
        "tte_years": 5.0 / 252.0,
        "residual_score_ready": True,
        "compression_active": False,
        "compression_ratio": 1.0,
    }
    target = trader._single_voucher_target("VEV_5300", snap, late_session=False)
    assert target < 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
```

Expected: FAIL if strategy-mode routing breaks the existing smile implementation.

- [ ] **Step 3: Write minimal implementation**

In `vev_trader_core.py`, make `_single_voucher_target()` route like this:

```python
        if self.STRATEGY_MODE == "zscore":
            return self._zscore_mode_target(voucher, snap, late_session)
        if self.STRATEGY_MODE == "black_scholes":
            return self._bs_single_vol_target(voucher, snap, late_session)
        if self.USE_NORMALIZED_RESIDUAL_SCORE:
            return self._normalized_residual_target(voucher, snap, late_session)
        return self._baseline_residual_delta_target(voucher, snap, late_session)
```

Keep the current smile-mode residual logic intact so the new `vev_trader_smile.py` is just the explicit standalone version of the strongest existing strategy family.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_vev_strategy_modes.py -q
python3 build_vev_variants.py
python3 -m py_compile vev_trader_smile.py
python3 -m py_compile vev_trader.py
```

Expected: tests PASS and both smile-based standalone files regenerate without syntax errors.

- [ ] **Step 5: Commit**

```bash
git add vev_trader_core.py build_vev_variants.py tests/test_vev_strategy_modes.py vev_trader_smile.py vev_trader.py
git commit -m "feat: promote standalone VEV smile trader"
```

### Task 6: Compare All Three Traders On Round 3 Data

**Files:**
- Create: `vev_trader_comparison.md`
- Modify: `vev_trader.py`
- Test: generated backtest JSON files in repo root or `/tmp`

- [ ] **Step 1: Write the failing test**

Create `vev_trader_comparison.md` with this required heading skeleton:

```markdown
# VEV Trader Comparison

| Trader | Day 0 | Day 1 | Day 2 | Split Total | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
```

Treat the absence of filled-in results as the failing condition for this task.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
test -s vev_trader_comparison.md && rg "vev_trader_(zscore|bs|smile)" vev_trader_comparison.md
```

Expected: FAIL because the comparison file either does not exist or has no filled-in trader results yet.

- [ ] **Step 3: Write minimal implementation**

Run the dedicated options backtester for all three standalone files:

```bash
python3 -m imc_backtester options vev_trader_zscore.py 3/ROUND_3 --day 0 --bootstrap-repetitions 0 --out /tmp/vev_zscore_day0.json
python3 -m imc_backtester options vev_trader_zscore.py 3/ROUND_3 --day 1 --bootstrap-repetitions 0 --out /tmp/vev_zscore_day1.json
python3 -m imc_backtester options vev_trader_zscore.py 3/ROUND_3 --day 2 --bootstrap-repetitions 0 --out /tmp/vev_zscore_day2.json
python3 -m imc_backtester options vev_trader_zscore.py 3/ROUND_3 --bootstrap-repetitions 0 --out /tmp/vev_zscore_split.json

python3 -m imc_backtester options vev_trader_bs.py 3/ROUND_3 --day 0 --bootstrap-repetitions 0 --out /tmp/vev_bs_day0.json
python3 -m imc_backtester options vev_trader_bs.py 3/ROUND_3 --day 1 --bootstrap-repetitions 0 --out /tmp/vev_bs_day1.json
python3 -m imc_backtester options vev_trader_bs.py 3/ROUND_3 --day 2 --bootstrap-repetitions 0 --out /tmp/vev_bs_day2.json
python3 -m imc_backtester options vev_trader_bs.py 3/ROUND_3 --bootstrap-repetitions 0 --out /tmp/vev_bs_split.json

python3 -m imc_backtester options vev_trader_smile.py 3/ROUND_3 --day 0 --bootstrap-repetitions 0 --out /tmp/vev_smile_day0.json
python3 -m imc_backtester options vev_trader_smile.py 3/ROUND_3 --day 1 --bootstrap-repetitions 0 --out /tmp/vev_smile_day1.json
python3 -m imc_backtester options vev_trader_smile.py 3/ROUND_3 --day 2 --bootstrap-repetitions 0 --out /tmp/vev_smile_day2.json
python3 -m imc_backtester options vev_trader_smile.py 3/ROUND_3 --bootstrap-repetitions 0 --out /tmp/vev_smile_split.json
```

Then fill `vev_trader_comparison.md` with the recorded results and notes, and keep `vev_trader.py` aligned with the best live candidate. If `vev_trader_smile.py` is tied-best on split total without clearly worse consistency, keep it as the promoted default.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
rg "vev_trader_zscore.py|vev_trader_bs.py|vev_trader_smile.py" vev_trader_comparison.md
python3 -m imc_backtester options vev_trader.py 3/ROUND_3 --bootstrap-repetitions 0 --out /tmp/vev_live_default.json
```

Expected: the comparison note contains all three traders and the promoted default backtests cleanly.

- [ ] **Step 5: Commit**

```bash
git add vev_trader.py vev_trader_comparison.md
git commit -m "feat: compare VEV traders and promote live default"
```
