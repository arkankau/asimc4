# Options Backtester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an options-first backtester package with explicit fair-value, persistent execution, and richer diagnostics while preserving legacy options entrypoints.

**Architecture:** Build a new `options_backtester` package around the existing Round 3 options data loader, move Black-Scholes and smile fitting into a dedicated fair-value module, add a persistent working-order execution engine, and keep `imc_backtester` as a compatibility surface for legacy options commands.

**Tech Stack:** Python 3, dataclasses, pytest, existing IMC-compatible datamodel and metrics helpers.

---

### Task 1: Add fair-value tests

**Files:**
- Create: `tests/test_options_fair_value.py`
- Modify: `options_backtester/fair_value.py`

- [ ] Write failing tests for smile-based signal marks, side-aware inventory marks, and liquidation marks.
- [ ] Run `python3 -m pytest tests/test_options_fair_value.py -q` and verify failure.
- [ ] Implement the minimal fair-value module to satisfy the tests.
- [ ] Re-run the same test file and verify it passes.

### Task 2: Add persistent execution tests

**Files:**
- Create: `tests/test_options_execution.py`
- Modify: `options_backtester/execution.py`

- [ ] Write failing tests for resting-order persistence, no same-tick passive fill, and later trade-through / queue-based fill behavior.
- [ ] Run `python3 -m pytest tests/test_options_execution.py -q` and verify failure.
- [ ] Implement the execution engine and fill reason tracking.
- [ ] Re-run the same test file and verify it passes.

### Task 3: Wire the options runner

**Files:**
- Create: `options_backtester/__init__.py`
- Create: `options_backtester/__main__.py`
- Create: `options_backtester/market.py`
- Create: `options_backtester/runner.py`
- Modify: `imc_backtester/__main__.py`

- [ ] Reuse the existing Round 3 loader and state builder through an options-first market module.
- [ ] Build the new options runner around the extracted fair-value and execution layers.
- [ ] Update the legacy `imc_backtester` options entrypoints to delegate to the new runner.
- [ ] Add runner-level output metadata for execution mode and mark modes.

### Task 4: Update docs and verify end-to-end

**Files:**
- Modify: `imc_backtester/README.md`

- [ ] Update the README to describe `options_backtester` as the primary options workflow and `imc_backtester` options mode as compatibility.
- [ ] Run focused tests for the new modules.
- [ ] Run one CLI smoke check against the Round 3 sample data and a local trader file.
- [ ] Inspect output metadata to confirm the new package is active.
