from __future__ import annotations

import argparse
import json
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from imc_backtester.datamodel import Observation, Trade, TradingState
from imc_backtester.metrics import compute_metrics_from_payload
from imc_backtester.runner import ACTIVITIES_HEADER, BacktestArtifacts, enforce_limits, load_trader_module, normalize_run_output

from .execution import PersistentExecutionEngine
from .fair_value import FairValueSnapshot, UNDERLYING, build_fair_value_snapshot
from .market import DAY_MODES, TIMESTAMP_MODES, _resolve_timestamp_mode, _round3_limits, _tte_days, build_state, load_options_csv_data

LIQUIDATION_COUNTERPARTY = "LIQUIDATION"
INVENTORY_MARK_MODES = ("signal", "conservative")
LIQUIDATION_MARK_MODES = ("signal", "haircut_close")
EXECUTION_MODES = ("conservative", "balanced", "optimistic")


@dataclass(frozen=True)
class OptionsDaySummary:
    day: int
    profit: float
    positions: list[dict[str, object]]
    start_tte_days: float
    end_tte_days: float


@dataclass(frozen=True)
class OptionsBacktestResult:
    artifacts: BacktestArtifacts
    day_summaries: list[OptionsDaySummary]
    positions_scope: str
    warnings: list[str]


def _make_state() -> TradingState:
    return TradingState(
        traderData="",
        timestamp=0,
        listings={},
        order_depths={},
        own_trades={},
        market_trades={},
        position={},
        observations=Observation(),
    )


def _apply_fills(fills: list[Trade], positions: dict[str, int], realized_cash: dict[str, float]) -> None:
    for fill in fills:
        if fill.buyer == "SUBMISSION":
            positions[fill.symbol] = positions.get(fill.symbol, 0) + fill.quantity
            realized_cash[fill.symbol] = realized_cash.get(fill.symbol, 0.0) - fill.price * fill.quantity
        elif fill.seller == "SUBMISSION":
            positions[fill.symbol] = positions.get(fill.symbol, 0) - fill.quantity
            realized_cash[fill.symbol] = realized_cash.get(fill.symbol, 0.0) + fill.price * fill.quantity


def _merge_trade_maps(*maps: dict[str, list[Trade]]) -> dict[str, list[Trade]]:
    merged: dict[str, list[Trade]] = {}
    for trade_map in maps:
        for symbol, trades in trade_map.items():
            merged.setdefault(symbol, []).extend(trades)
    for trades in merged.values():
        trades.sort(key=lambda trade: (trade.timestamp, trade.symbol, trade.price, trade.quantity))
    return merged


def _trade_to_dict(trade: Trade, output_timestamp: int) -> dict[str, object]:
    return {
        "timestamp": output_timestamp,
        "buyer": trade.buyer,
        "seller": trade.seller,
        "symbol": trade.symbol,
        "currency": "XIRECS",
        "price": float(trade.price),
        "quantity": trade.quantity,
    }


def _format_activity_row(snapshot, global_timestamp: int, profit: float) -> str:
    columns = [
        snapshot.day,
        global_timestamp,
        snapshot.product,
        snapshot.bid_prices[0] if len(snapshot.bid_prices) > 0 else "",
        snapshot.bid_volumes[0] if len(snapshot.bid_volumes) > 0 else "",
        snapshot.bid_prices[1] if len(snapshot.bid_prices) > 1 else "",
        snapshot.bid_volumes[1] if len(snapshot.bid_volumes) > 1 else "",
        snapshot.bid_prices[2] if len(snapshot.bid_prices) > 2 else "",
        snapshot.bid_volumes[2] if len(snapshot.bid_volumes) > 2 else "",
        snapshot.ask_prices[0] if len(snapshot.ask_prices) > 0 else "",
        snapshot.ask_volumes[0] if len(snapshot.ask_volumes) > 0 else "",
        snapshot.ask_prices[1] if len(snapshot.ask_prices) > 1 else "",
        snapshot.ask_volumes[1] if len(snapshot.ask_volumes) > 1 else "",
        snapshot.ask_prices[2] if len(snapshot.ask_prices) > 2 else "",
        snapshot.ask_volumes[2] if len(snapshot.ask_volumes) > 2 else "",
        snapshot.mid_price,
        profit,
    ]
    return ";".join(str(value) for value in columns)


def _build_positions(products: list[str], realized_cash: dict[str, float], positions: dict[str, int]) -> list[dict[str, object]]:
    return [
        {"symbol": "XIRECS", "quantity": int(round(sum(realized_cash.values())))},
        *({"symbol": product, "quantity": positions.get(product, 0)} for product in products),
    ]


def _serialize_valuation(valuation: FairValueSnapshot) -> dict[str, object]:
    return {
        "signalMarks": valuation.signal_marks,
        "inventoryMarks": valuation.inventory_marks,
        "liquidationMarks": valuation.liquidation_marks,
        "diagnostics": {product: asdict(diag) for product, diag in valuation.diagnostics.items()},
    }


def _select_inventory_marks(valuation: FairValueSnapshot, inventory_mark_mode: str) -> dict[str, float]:
    if inventory_mark_mode == "signal":
        return valuation.signal_marks
    if inventory_mark_mode == "conservative":
        return valuation.inventory_marks
    raise ValueError(f"Unsupported inventory mark mode: {inventory_mark_mode}")


def _select_liquidation_marks(valuation: FairValueSnapshot, liquidation_mark_mode: str) -> dict[str, float]:
    if liquidation_mark_mode == "signal":
        return valuation.signal_marks
    if liquidation_mark_mode == "haircut_close":
        return valuation.liquidation_marks
    raise ValueError(f"Unsupported liquidation mark mode: {liquidation_mark_mode}")


def _settle_inventory(
    *,
    products: list[str],
    positions: dict[str, int],
    realized_cash: dict[str, float],
    settlement_marks: dict[str, float],
    output_trades: list[dict[str, object]],
    output_timestamp: int,
) -> None:
    for product in products:
        quantity = positions.get(product, 0)
        if quantity == 0:
            continue

        settlement_price = float(settlement_marks.get(product, 0.0))
        if quantity > 0:
            realized_cash[product] += settlement_price * quantity
            output_trades.append(
                {
                    "timestamp": output_timestamp,
                    "buyer": LIQUIDATION_COUNTERPARTY,
                    "seller": "SUBMISSION",
                    "symbol": product,
                    "currency": "XIRECS",
                    "price": settlement_price,
                    "quantity": quantity,
                }
            )
        else:
            cover_quantity = -quantity
            realized_cash[product] -= settlement_price * cover_quantity
            output_trades.append(
                {
                    "timestamp": output_timestamp,
                    "buyer": "SUBMISSION",
                    "seller": LIQUIDATION_COUNTERPARTY,
                    "symbol": product,
                    "currency": "XIRECS",
                    "price": settlement_price,
                    "quantity": cover_quantity,
                }
            )
        positions[product] = 0


def _run_options_sequence(
    trader: Any,
    csv_data,
    timestamps: list[int],
    *,
    limits: dict[str, int],
    timestamp_mode: str,
    expiry_days_at_start: float,
    execution_mode: str,
    inventory_mark_mode: str,
    liquidation_mark_mode: str,
    graph_profit_offset: float = 0.0,
) -> BacktestArtifacts:
    state = _make_state()
    execution = PersistentExecutionEngine(mode=execution_mode)
    realized_cash = {product: 0.0 for product in csv_data.products}
    previous_signal_marks = {product: 0.0 for product in csv_data.products}
    logs: list[dict[str, object]] = []
    activities_rows = [ACTIVITIES_HEADER]
    graph_points = ["timestamp;value"]
    output_trades: list[dict[str, object]] = []

    for global_timestamp in timestamps:
        snapshots = csv_data.prices[global_timestamp]
        passive_result = execution.process_resting_orders(
            snapshots=snapshots,
            tape_trades=csv_data.trade_history.get(global_timestamp, {}),
            timestamp=csv_data.local_timestamp_by_global_timestamp[global_timestamp]
            if timestamp_mode == "local"
            else global_timestamp,
        )
        passive_fills = [trade for trades in passive_result.own_trades.values() for trade in trades]
        _apply_fills(passive_fills, state.position, realized_cash)

        build_state(csv_data, global_timestamp, state, timestamp_mode, expiry_days_at_start)
        state.own_trades = passive_result.own_trades
        state.market_trades = passive_result.market_trades

        stdout = StringIO()
        with redirect_stdout(stdout):
            raw_output = trader.run(state)

        desired_orders, trader_data = normalize_run_output(raw_output)
        sandbox_messages = enforce_limits(desired_orders, state.position, limits)
        aggressive_result = execution.reconcile_target_orders(
            desired_orders=desired_orders,
            snapshots=snapshots,
            timestamp=csv_data.local_timestamp_by_global_timestamp[global_timestamp]
            if timestamp_mode == "local"
            else global_timestamp,
        )
        _apply_fills(aggressive_result.aggressive_fills, state.position, realized_cash)

        aggressive_map = _merge_trade_maps(
            {
                trade.symbol: [trade]
                for trade in aggressive_result.aggressive_fills
            }
        ) if aggressive_result.aggressive_fills else {}
        combined_own_trades = _merge_trade_maps(passive_result.own_trades, aggressive_map)
        state.own_trades = combined_own_trades
        state.market_trades = passive_result.market_trades
        state.traderData = trader_data

        for trades in combined_own_trades.values():
            output_trades.extend(
                _trade_to_dict(
                    trade,
                    global_timestamp,
                )
                for trade in trades
            )
        for trades in passive_result.market_trades.values():
            output_trades.extend(_trade_to_dict(trade, global_timestamp) for trade in trades)

        valuation = build_fair_value_snapshot(
            snapshots=snapshots,
            previous_marks=previous_signal_marks,
            positions=state.position,
            expiry_days_at_start=expiry_days_at_start,
            global_timestamp=global_timestamp,
        )
        previous_signal_marks = dict(valuation.signal_marks)
        inventory_marks = _select_inventory_marks(valuation, inventory_mark_mode)

        total_profit = 0.0
        per_product_pnl: dict[str, float] = {}
        for product in csv_data.products:
            snapshot = snapshots.get(product)
            if snapshot is None:
                continue
            marked_profit = realized_cash[product] + state.position.get(product, 0) * inventory_marks.get(product, 0.0)
            per_product_pnl[product] = marked_profit
            activities_rows.append(_format_activity_row(snapshot, global_timestamp, marked_profit))
            total_profit += marked_profit

        graph_points.append(f"{global_timestamp};{graph_profit_offset + total_profit}")
        logs.append(
            {
                "sandboxLog": "\n".join(sandbox_messages),
                "lambdaLog": stdout.getvalue().rstrip(),
                "timestamp": global_timestamp,
                "fillEvents": [asdict(event) for event in passive_result.fill_events + aggressive_result.fill_events],
                "valuation": _serialize_valuation(valuation),
                "restingOrders": {
                    symbol: [asdict(order) for order in orders]
                    for symbol, orders in execution.snapshot().items()
                },
                "perProductPnl": per_product_pnl,
            }
        )

    final_timestamp = timestamps[-1]
    final_valuation = build_fair_value_snapshot(
        snapshots=csv_data.prices[final_timestamp],
        previous_marks=previous_signal_marks,
        positions=state.position,
        expiry_days_at_start=expiry_days_at_start,
        global_timestamp=final_timestamp,
    )
    settlement_marks = _select_liquidation_marks(final_valuation, liquidation_mark_mode)
    _settle_inventory(
        products=csv_data.products,
        positions=state.position,
        realized_cash=realized_cash,
        settlement_marks=settlement_marks,
        output_trades=output_trades,
        output_timestamp=final_timestamp,
    )

    positions = _build_positions(csv_data.products, realized_cash, state.position)
    final_profit = float(sum(realized_cash.values()))
    output_trades.sort(key=lambda trade: (int(trade["timestamp"]), str(trade["symbol"]), float(trade["price"]), int(trade["quantity"])))

    return BacktestArtifacts(
        activities_log="\n".join(activities_rows),
        graph_log="\n".join(graph_points),
        trade_history=output_trades,
        logs=logs,
        positions=positions,
        profit=final_profit,
    )


def run_backtest(
    algorithm_path: Path,
    csv_data,
    *,
    limits: dict[str, int],
    timestamp_mode: str,
    expiry_days_at_start: float,
    day_mode: str,
    execution_mode: str,
    inventory_mark_mode: str,
    liquidation_mark_mode: str,
) -> OptionsBacktestResult:
    trader_module = load_trader_module(algorithm_path)
    effective_timestamp_mode, warnings = _resolve_timestamp_mode(day_mode, timestamp_mode)
    warnings = [
        "Options-first runner active: persistent passive orders, smile-based valuation diagnostics, and explicit liquidation marks.",
        *warnings,
    ]

    if day_mode == "continuous":
        artifacts = _run_options_sequence(
            trader=trader_module.Trader(),
            csv_data=csv_data,
            timestamps=csv_data.timestamps,
            limits=limits,
            timestamp_mode=effective_timestamp_mode,
            expiry_days_at_start=expiry_days_at_start,
            execution_mode=execution_mode,
            inventory_mark_mode=inventory_mark_mode,
            liquidation_mark_mode=liquidation_mark_mode,
        )
        first_timestamp = csv_data.timestamps[0]
        last_timestamp = csv_data.timestamps[-1]
        first_day = csv_data.day_by_global_timestamp[first_timestamp]
        last_day = csv_data.day_by_global_timestamp[last_timestamp]
        return OptionsBacktestResult(
            artifacts=artifacts,
            day_summaries=[
                OptionsDaySummary(
                    day=first_day if first_day == last_day else -1,
                    profit=artifacts.profit,
                    positions=artifacts.positions,
                    start_tte_days=_tte_days(expiry_days_at_start, first_timestamp),
                    end_tte_days=_tte_days(expiry_days_at_start, last_timestamp),
                )
            ],
            positions_scope="final_sequence_post_liquidation_flat",
            warnings=warnings,
        )

    timestamps_by_day: dict[int, list[int]] = {}
    for global_timestamp in csv_data.timestamps:
        day = csv_data.day_by_global_timestamp[global_timestamp]
        timestamps_by_day.setdefault(day, []).append(global_timestamp)

    combined_activities_rows = [ACTIVITIES_HEADER]
    combined_graph_points = ["timestamp;value"]
    combined_trade_history: list[dict[str, object]] = []
    combined_logs: list[dict[str, object]] = []
    day_summaries: list[OptionsDaySummary] = []
    cumulative_profit = 0.0
    for day in sorted(timestamps_by_day):
        day_timestamps = timestamps_by_day[day]
        day_artifacts = _run_options_sequence(
            trader=trader_module.Trader(),
            csv_data=csv_data,
            timestamps=day_timestamps,
            limits=limits,
            timestamp_mode=effective_timestamp_mode,
            expiry_days_at_start=expiry_days_at_start,
            execution_mode=execution_mode,
            inventory_mark_mode=inventory_mark_mode,
            liquidation_mark_mode=liquidation_mark_mode,
            graph_profit_offset=cumulative_profit,
        )
        combined_activities_rows.extend(day_artifacts.activities_log.splitlines()[1:])
        combined_graph_points.extend(day_artifacts.graph_log.splitlines()[1:])
        combined_trade_history.extend(day_artifacts.trade_history)
        combined_logs.extend(day_artifacts.logs)
        cumulative_profit += day_artifacts.profit
        day_summaries.append(
            OptionsDaySummary(
                day=day,
                profit=day_artifacts.profit,
                positions=day_artifacts.positions,
                start_tte_days=_tte_days(expiry_days_at_start, day_timestamps[0]),
                end_tte_days=_tte_days(expiry_days_at_start, day_timestamps[-1]),
            )
        )

    return OptionsBacktestResult(
        artifacts=BacktestArtifacts(
            activities_log="\n".join(combined_activities_rows),
            graph_log="\n".join(combined_graph_points),
            trade_history=combined_trade_history,
            logs=combined_logs,
            positions=[
                {"symbol": "XIRECS", "quantity": int(round(cumulative_profit))},
                *({"symbol": product, "quantity": 0} for product in csv_data.products),
            ],
            profit=float(cumulative_profit),
        ),
        day_summaries=day_summaries,
        positions_scope="split_cumulative_post_liquidation_flattened",
        warnings=warnings,
    )


def build_output_payload(
    result: OptionsBacktestResult,
    *,
    data_dir: Path,
    days: set[int] | None,
    products: list[str],
    requested_timestamp_mode: str,
    effective_timestamp_mode: str,
    expiry_days_at_start: float,
    day_mode: str,
    execution_mode: str,
    inventory_mark_mode: str,
    liquidation_mark_mode: str,
) -> dict[str, object]:
    vouchers = [product for product in products if product != UNDERLYING]
    artifacts = result.artifacts
    return {
        "round": "local",
        "status": "FINISHED",
        "profit": artifacts.profit,
        "activitiesLog": artifacts.activities_log,
        "graphLog": artifacts.graph_log,
        "tradeHistory": artifacts.trade_history,
        "logs": artifacts.logs,
        "positions": artifacts.positions,
        "daySummaries": [
            {
                "day": summary.day,
                "profit": summary.profit,
                "positions": summary.positions,
                "start_tte_days": summary.start_tte_days,
                "end_tte_days": summary.end_tte_days,
            }
            for summary in result.day_summaries
        ],
        "warnings": result.warnings,
        "backtestType": "options_backtester_round3_vev",
        "backtestMetadata": {
            "data_dir": str(data_dir),
            "days": sorted(days) if days is not None else "all",
            "requested_timestamp_mode": requested_timestamp_mode,
            "effective_timestamp_mode": effective_timestamp_mode,
            "expiry_days_at_start": expiry_days_at_start,
            "day_mode": day_mode,
            "execution_mode": execution_mode,
            "inventory_mark_mode": inventory_mark_mode,
            "liquidation_mark_mode": liquidation_mark_mode,
            "settles_inventory": True,
            "positions_scope": result.positions_scope,
            "universe": {
                "underlying": UNDERLYING,
                "products": products,
                "vouchers": vouchers,
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay the Round 3 VEV options universe with persistent quotes and smile-based valuation diagnostics."
    )
    parser.add_argument("algorithm", type=Path, help="Path to the Trader algorithm .py file")
    parser.add_argument("data_dir", type=Path, help="Directory containing prices_round_3_day_*.csv and trades_round_3_day_*.csv")
    parser.add_argument("--out", type=Path, help="Optional path for the generated result JSON")
    parser.add_argument("--day", action="append", type=int, default=[], help="Optional day filter; repeat to select multiple days")
    parser.add_argument("--timestamp-mode", choices=TIMESTAMP_MODES, default="local")
    parser.add_argument("--day-mode", choices=DAY_MODES, default="split")
    parser.add_argument("--expiry-days-at-start", type=float, default=8.0)
    parser.add_argument("--default-limit", type=int, default=80)
    parser.add_argument("--limit", action="append", default=[], metavar="PRODUCT=LIMIT")
    parser.add_argument("--execution-mode", choices=EXECUTION_MODES, default="conservative")
    parser.add_argument("--inventory-mark-mode", choices=INVENTORY_MARK_MODES, default="conservative")
    parser.add_argument("--liquidation-mark-mode", choices=LIQUIDATION_MARK_MODES, default="haircut_close")
    parser.add_argument("--bootstrap-repetitions", type=int, default=1000)
    parser.add_argument("--bootstrap-block-size", type=int, default=10)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args(argv)

    selected_days = set(args.day) if args.day else None
    csv_data = load_options_csv_data(args.data_dir, days=selected_days)
    limits = _round3_limits(csv_data.products, args.default_limit, args.limit)
    effective_timestamp_mode, _warnings = _resolve_timestamp_mode(args.day_mode, args.timestamp_mode)
    result = run_backtest(
        algorithm_path=args.algorithm.expanduser().resolve(),
        csv_data=csv_data,
        limits=limits,
        timestamp_mode=args.timestamp_mode,
        expiry_days_at_start=args.expiry_days_at_start,
        day_mode=args.day_mode,
        execution_mode=args.execution_mode,
        inventory_mark_mode=args.inventory_mark_mode,
        liquidation_mark_mode=args.liquidation_mark_mode,
    )
    payload = build_output_payload(
        result,
        data_dir=args.data_dir.expanduser().resolve(),
        days=selected_days,
        products=csv_data.products,
        requested_timestamp_mode=args.timestamp_mode,
        effective_timestamp_mode=effective_timestamp_mode,
        expiry_days_at_start=args.expiry_days_at_start,
        day_mode=args.day_mode,
        execution_mode=args.execution_mode,
        inventory_mark_mode=args.inventory_mark_mode,
        liquidation_mark_mode=args.liquidation_mark_mode,
    )
    payload["metrics"] = compute_metrics_from_payload(
        payload,
        source_path=str(args.data_dir.expanduser().resolve()),
        bootstrap_repetitions=args.bootstrap_repetitions,
        bootstrap_block_size=args.bootstrap_block_size,
        bootstrap_seed=args.bootstrap_seed,
    )

    out_path = args.out.expanduser().resolve() if args.out else Path.cwd() / f"{args.algorithm.stem}.options.backtest.json"
    out_path.write_text(json.dumps(payload, indent=2))

    print(f"Wrote options replay result to {out_path}")
    print(f"Profit: {result.artifacts.profit:.4f}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
