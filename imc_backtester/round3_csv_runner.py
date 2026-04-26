from __future__ import annotations

import argparse
import csv
import json
import math
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .datamodel import Listing, Observation, OrderDepth, TradingState, Trade
from .log_parser import PriceSnapshot, TapeTrade
from .metrics import compute_metrics_from_payload
from .runner import (
    ACTIVITIES_HEADER,
    BacktestArtifacts,
    enforce_limits,
    load_trader_module,
    match_orders_for_product,
    normalize_run_output,
)

UNDERLYING = "VELVETFRUIT_EXTRACT"
ROUND3_SPOT_LIMITS = {
    "VELVETFRUIT_EXTRACT": 200,
    "HYDROGEL_PACK": 200,
}
VOUCHER_LIMIT = 300
VEGA_FLOOR = 0.25
IMPLIED_VOL_MAX = 3.0
MARK_MODES = ("mid", "conservative", "intrinsic", "smile")
TIMESTAMP_MODES = ("local", "global")


@dataclass(frozen=True)
class Round3CsvData:
    products: list[str]
    timestamps: list[int]
    prices: dict[int, dict[str, PriceSnapshot]]
    trade_history: dict[int, dict[str, list[TapeTrade]]]
    day_by_global_timestamp: dict[int, int]
    local_timestamp_by_global_timestamp: dict[int, int]


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    return int(float(cleaned))


def _extract_day_from_filename(path: Path) -> int:
    stem = path.stem
    marker = "day_"
    if marker not in stem:
        raise ValueError(f"Could not infer day from filename: {path.name}")
    return int(stem.split(marker, 1)[1])


def _global_timestamp(day: int, local_timestamp: int) -> int:
    return day * 1_000_000 + local_timestamp


def _parse_voucher_strike(symbol: str) -> int | None:
    if not symbol.startswith("VEV_"):
        return None
    suffix = symbol[4:]
    return int(suffix) if suffix.isdigit() else None


def _best_bid(snapshot: PriceSnapshot) -> int | None:
    return snapshot.bid_prices[0] if snapshot.bid_prices else None


def _best_ask(snapshot: PriceSnapshot) -> int | None:
    return snapshot.ask_prices[0] if snapshot.ask_prices else None


def _base_mark(snapshot: PriceSnapshot, previous_mark: float) -> float:
    if snapshot.mid_price > 0:
        return snapshot.mid_price

    best_bid = _best_bid(snapshot)
    best_ask = _best_ask(snapshot)
    if best_bid is not None and best_ask is not None:
        return 0.5 * (best_bid + best_ask)

    return previous_mark


def load_round3_csv_data(data_dir: Path, days: set[int] | None = None) -> Round3CsvData:
    directory = data_dir.expanduser().resolve()
    price_files = sorted(directory.glob("prices_round_3_day_*.csv"))
    trade_files = sorted(directory.glob("trades_round_3_day_*.csv"))
    if not price_files:
        raise FileNotFoundError(f"No Round 3 price CSVs found in {directory}")

    products: list[str] = []
    prices: dict[int, dict[str, PriceSnapshot]] = {}
    day_by_global_timestamp: dict[int, int] = {}
    local_timestamp_by_global_timestamp: dict[int, int] = {}

    for path in price_files:
        file_day = _extract_day_from_filename(path)
        if days is not None and file_day not in days:
            continue

        with path.open() as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                day = int(row["day"])
                if days is not None and day not in days:
                    continue

                local_timestamp = int(row["timestamp"])
                global_timestamp = _global_timestamp(day, local_timestamp)
                product = row["product"]
                if product not in products:
                    products.append(product)

                bid_prices: list[int] = []
                bid_volumes: list[int] = []
                ask_prices: list[int] = []
                ask_volumes: list[int] = []
                for level in (1, 2, 3):
                    bid_price = _parse_optional_int(row.get(f"bid_price_{level}"))
                    bid_volume = _parse_optional_int(row.get(f"bid_volume_{level}"))
                    ask_price = _parse_optional_int(row.get(f"ask_price_{level}"))
                    ask_volume = _parse_optional_int(row.get(f"ask_volume_{level}"))
                    if bid_price is not None and bid_volume is not None:
                        bid_prices.append(bid_price)
                        bid_volumes.append(bid_volume)
                    if ask_price is not None and ask_volume is not None:
                        ask_prices.append(ask_price)
                        ask_volumes.append(ask_volume)

                prices.setdefault(global_timestamp, {})[product] = PriceSnapshot(
                    day=day,
                    timestamp=local_timestamp,
                    product=product,
                    bid_prices=bid_prices,
                    bid_volumes=bid_volumes,
                    ask_prices=ask_prices,
                    ask_volumes=ask_volumes,
                    mid_price=float(row["mid_price"]),
                )
                day_by_global_timestamp[global_timestamp] = day
                local_timestamp_by_global_timestamp[global_timestamp] = local_timestamp

    trade_history: dict[int, dict[str, list[TapeTrade]]] = {}
    for path in trade_files:
        file_day = _extract_day_from_filename(path)
        if days is not None and file_day not in days:
            continue

        with path.open() as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                day = file_day
                if days is not None and day not in days:
                    continue

                local_timestamp = int(row["timestamp"])
                global_timestamp = _global_timestamp(day, local_timestamp)
                trade = TapeTrade(
                    timestamp=local_timestamp,
                    buyer=row.get("buyer", "") or "",
                    seller=row.get("seller", "") or "",
                    symbol=row["symbol"],
                    currency=row.get("currency", "") or "",
                    price=int(round(float(row["price"]))),
                    quantity=int(row["quantity"]),
                )
                trade_history.setdefault(global_timestamp, {}).setdefault(trade.symbol, []).append(trade)

    for trades_by_symbol in trade_history.values():
        for trades in trades_by_symbol.values():
            trades.sort(key=lambda trade: (trade.timestamp, trade.price, trade.quantity, trade.buyer, trade.seller))

    timestamps = sorted(prices)
    if not timestamps:
        selected = sorted(days) if days else "all"
        raise ValueError(f"No Round 3 price rows found after filtering days={selected}")

    return Round3CsvData(
        products=products,
        timestamps=timestamps,
        prices=prices,
        trade_history=trade_history,
        day_by_global_timestamp=day_by_global_timestamp,
        local_timestamp_by_global_timestamp=local_timestamp_by_global_timestamp,
    )


def build_state(
    data: Round3CsvData,
    global_timestamp: int,
    state: TradingState,
    timestamp_mode: str,
    expiry_days_at_start: float,
) -> None:
    local_timestamp = data.local_timestamp_by_global_timestamp[global_timestamp]
    state.timestamp = local_timestamp if timestamp_mode == "local" else global_timestamp
    state.listings = {}
    state.order_depths = {}

    day = data.day_by_global_timestamp[global_timestamp]
    tte_millidays = int(round(max(0.0, expiry_days_at_start - global_timestamp / 1_000_000.0) * 1000.0))
    state.observations = Observation(
        plainValueObservations={
            "ROUND3_DAY": day,
            "ROUND3_LOCAL_TIMESTAMP": local_timestamp,
            "ROUND3_GLOBAL_TIMESTAMP": global_timestamp,
            "ROUND3_TTE_MILLIDAYS": tte_millidays,
        }
    )

    for product in data.products:
        snapshot = data.prices[global_timestamp].get(product)
        if snapshot is None:
            continue

        depth = state.order_depths.setdefault(product, OrderDepth())
        for price, volume in zip(snapshot.bid_prices, snapshot.bid_volumes):
            depth.buy_orders[price] = volume
        for price, volume in zip(snapshot.ask_prices, snapshot.ask_volumes):
            depth.sell_orders[price] = -volume
        state.listings[product] = Listing(symbol=product, product=product, denomination="XIRECS")


def _format_activity_row(snapshot: PriceSnapshot, global_timestamp: int, profit: float) -> str:
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


def _trade_to_output_dict(trade: Trade, output_timestamp: int) -> dict[str, object]:
    return {
        "timestamp": output_timestamp,
        "buyer": trade.buyer,
        "seller": trade.seller,
        "symbol": trade.symbol,
        "currency": "XIRECS",
        "price": float(trade.price),
        "quantity": trade.quantity,
    }


def _round3_limits(products: list[str], default_limit: int, overrides: list[str]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for product in products:
        strike = _parse_voucher_strike(product)
        if strike is not None:
            limits[product] = VOUCHER_LIMIT
        else:
            limits[product] = ROUND3_SPOT_LIMITS.get(product, default_limit)

    for raw in overrides:
        if "=" not in raw:
            raise ValueError(f"Invalid --limit value '{raw}', expected PRODUCT=LIMIT")
        product, value = raw.split("=", 1)
        limits[product] = int(value)

    return limits


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_call_price(spot: float, strike: float, tte: float, sigma: float) -> float:
    intrinsic = max(spot - strike, 0.0)
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return intrinsic

    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * _norm_cdf(d1) - strike * _norm_cdf(d2)


def _bs_vega(spot: float, strike: float, tte: float, sigma: float) -> float:
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return 0.0
    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    return spot * _norm_pdf(d1) * math.sqrt(tte)


def _implied_vol(price: float, spot: float, strike: float, tte: float, sigma_init: float = 0.25) -> float | None:
    intrinsic = max(spot - strike, 0.0)
    if tte <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return None
    if price <= intrinsic + 0.5:
        return None

    sigma = min(IMPLIED_VOL_MAX, max(0.02, sigma_init))
    for _ in range(20):
        model = _bs_call_price(spot, strike, tte, sigma)
        vega = _bs_vega(spot, strike, tte, sigma)
        if vega < VEGA_FLOOR:
            return None
        step = (model - price) / vega
        sigma = min(IMPLIED_VOL_MAX, max(0.02, sigma - step))
        if abs(step) < 1e-5:
            break

    if _bs_vega(spot, strike, tte, sigma) < VEGA_FLOOR:
        return None
    return sigma


def _fit_weighted_quadratic(points: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    if len(points) < 4:
        return None

    s0 = s1 = s2 = s3 = s4 = 0.0
    t0 = t1 = t2 = 0.0
    for x, y, w in points:
        w = max(1e-6, w)
        x2 = x * x
        s0 += w
        s1 += w * x
        s2 += w * x2
        s3 += w * x2 * x
        s4 += w * x2 * x2
        t0 += w * y
        t1 += w * x * y
        t2 += w * x2 * y

    matrix = [
        [s0, s1, s2, t0],
        [s1, s2, s3, t1],
        [s2, s3, s4, t2],
    ]

    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(matrix[row][col]))
        if abs(matrix[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            matrix[col], matrix[pivot] = matrix[pivot], matrix[col]

        pivot_value = matrix[col][col]
        for idx in range(col, 4):
            matrix[col][idx] /= pivot_value

        for row in range(3):
            if row == col:
                continue
            factor = matrix[row][col]
            for idx in range(col, 4):
                matrix[row][idx] -= factor * matrix[col][idx]

    return matrix[0][3], matrix[1][3], matrix[2][3]


def _smile_marks(
    snapshots: dict[str, PriceSnapshot],
    previous_marks: dict[str, float],
    tte_years: float,
) -> dict[str, float]:
    marks = {product: _base_mark(snapshot, previous_marks.get(product, 0.0)) for product, snapshot in snapshots.items()}
    if tte_years <= 0.0:
        return marks

    spot = marks.get(UNDERLYING)
    if spot is None or spot <= 0.0:
        return marks

    fit_points: list[tuple[str, int, float, float, float]] = []
    for product, snapshot in snapshots.items():
        strike = _parse_voucher_strike(product)
        if strike is None:
            continue
        mid = marks[product]
        iv = _implied_vol(mid, spot, float(strike), tte_years)
        if iv is None:
            continue
        vega = _bs_vega(spot, float(strike), tte_years, iv)
        if vega < VEGA_FLOOR:
            continue
        moneyness = math.log(spot / float(strike))
        fit_points.append((product, strike, moneyness, iv, vega))

    coeffs = _fit_weighted_quadratic([(m, iv, vega) for _product, _strike, m, iv, vega in fit_points])
    if coeffs is None:
        return marks

    a0, a1, a2 = coeffs
    for product, snapshot in snapshots.items():
        strike = _parse_voucher_strike(product)
        if strike is None:
            continue
        moneyness = math.log(spot / float(strike))
        fitted_iv = max(0.05, min(IMPLIED_VOL_MAX, a0 + a1 * moneyness + a2 * moneyness * moneyness))
        marks[product] = _bs_call_price(spot, float(strike), tte_years, fitted_iv)

    return marks


def mark_products(
    snapshots: dict[str, PriceSnapshot],
    previous_marks: dict[str, float],
    positions: dict[str, int],
    mark_mode: str,
    expiry_days_at_start: float,
    global_timestamp: int,
) -> dict[str, float]:
    marks = {product: _base_mark(snapshot, previous_marks.get(product, 0.0)) for product, snapshot in snapshots.items()}
    if mark_mode == "mid":
        return marks

    if mark_mode == "conservative":
        for product, snapshot in snapshots.items():
            position = positions.get(product, 0)
            best_bid = _best_bid(snapshot)
            best_ask = _best_ask(snapshot)
            if position > 0 and best_bid is not None:
                marks[product] = float(best_bid)
            elif position < 0 and best_ask is not None:
                marks[product] = float(best_ask)
        return marks

    spot = marks.get(UNDERLYING)
    if spot is None or spot <= 0.0:
        return marks

    if mark_mode == "intrinsic":
        for product in list(marks):
            strike = _parse_voucher_strike(product)
            if strike is not None:
                marks[product] = max(spot - strike, 0.0)
        return marks

    if mark_mode == "smile":
        tte_years = max(0.0, expiry_days_at_start - global_timestamp / 1_000_000.0) / 252.0
        return _smile_marks(snapshots, previous_marks, tte_years)

    raise ValueError(f"Unsupported mark mode: {mark_mode}")


def run_backtest(
    algorithm_path: Path,
    csv_data: Round3CsvData,
    *,
    limits: dict[str, int],
    match_trades: str,
    mark_mode: str,
    timestamp_mode: str,
    expiry_days_at_start: float,
) -> BacktestArtifacts:
    trader_module = load_trader_module(algorithm_path)
    trader = trader_module.Trader()

    state = TradingState(
        traderData="",
        timestamp=0,
        listings={},
        order_depths={},
        own_trades={},
        market_trades={},
        position={},
        observations=Observation(),
    )

    realized_cash = {product: 0.0 for product in csv_data.products}
    mark_prices = {product: 0.0 for product in csv_data.products}
    logs: list[dict[str, object]] = []
    activities_rows = [ACTIVITIES_HEADER]
    graph_points = ["timestamp;value"]
    output_trades: list[dict[str, object]] = []

    for global_timestamp in csv_data.timestamps:
        build_state(csv_data, global_timestamp, state, timestamp_mode, expiry_days_at_start)
        stdout = StringIO()
        with redirect_stdout(stdout):
            raw_output = trader.run(state)

        orders, trader_data = normalize_run_output(raw_output)
        sandbox_messages = enforce_limits(orders, state.position, limits)
        logs.append(
            {
                "sandboxLog": "\n".join(sandbox_messages),
                "lambdaLog": stdout.getvalue().rstrip(),
                "timestamp": global_timestamp,
            }
        )

        current_market_trades: dict[str, list[Trade]] = {}
        current_own_trades: dict[str, list[Trade]] = {}
        for product in csv_data.products:
            fills, remaining_market_trades = match_orders_for_product(
                product=product,
                product_orders=orders.get(product, []),
                state=state,
                tape_trades=csv_data.trade_history.get(global_timestamp, {}).get(product, []),
                realized_cash=realized_cash,
                match_trades=match_trades,
                submission_trade_mode="full",
            )

            if fills:
                current_own_trades[product] = fills
                output_trades.extend(_trade_to_output_dict(fill, global_timestamp) for fill in fills)

            if remaining_market_trades:
                localized = [
                    Trade(
                        symbol=trade.symbol,
                        price=trade.price,
                        quantity=trade.quantity,
                        buyer=trade.buyer,
                        seller=trade.seller,
                        timestamp=csv_data.local_timestamp_by_global_timestamp[global_timestamp]
                        if timestamp_mode == "local"
                        else global_timestamp,
                    )
                    for trade in remaining_market_trades
                ]
                current_market_trades[product] = localized
                output_trades.extend(_trade_to_output_dict(trade, global_timestamp) for trade in remaining_market_trades)

        state.own_trades = current_own_trades
        state.market_trades = current_market_trades
        state.traderData = trader_data

        snapshots = csv_data.prices[global_timestamp]
        marks = mark_products(
            snapshots=snapshots,
            previous_marks=mark_prices,
            positions=state.position,
            mark_mode=mark_mode,
            expiry_days_at_start=expiry_days_at_start,
            global_timestamp=global_timestamp,
        )

        total_profit = 0.0
        for product in csv_data.products:
            snapshot = snapshots.get(product)
            if snapshot is None:
                continue
            mark_prices[product] = marks.get(product, mark_prices.get(product, 0.0))
            marked_profit = realized_cash[product] + state.position.get(product, 0) * mark_prices[product]
            activities_rows.append(_format_activity_row(snapshot, global_timestamp, marked_profit))
            total_profit += marked_profit

        graph_points.append(f"{global_timestamp};{total_profit}")

    positions = [
        {"symbol": "XIRECS", "quantity": int(sum(realized_cash.values()))},
        *({"symbol": product, "quantity": state.position.get(product, 0)} for product in csv_data.products),
    ]
    final_profit = float(
        sum(realized_cash[product] + state.position.get(product, 0) * mark_prices[product] for product in csv_data.products)
    )
    output_trades.sort(
        key=lambda trade: (int(trade["timestamp"]), str(trade["symbol"]), float(trade["price"]), int(trade["quantity"]))
    )

    return BacktestArtifacts(
        activities_log="\n".join(activities_rows),
        graph_log="\n".join(graph_points),
        trade_history=output_trades,
        logs=logs,
        positions=positions,
        profit=final_profit,
    )


def build_output_payload(
    artifacts: BacktestArtifacts,
    *,
    data_dir: Path,
    days: set[int] | None,
    mark_mode: str,
    timestamp_mode: str,
    expiry_days_at_start: float,
) -> dict[str, object]:
    return {
        "round": "local",
        "status": "FINISHED",
        "profit": artifacts.profit,
        "activitiesLog": artifacts.activities_log,
        "graphLog": artifacts.graph_log,
        "tradeHistory": artifacts.trade_history,
        "logs": artifacts.logs,
        "positions": artifacts.positions,
        "backtestType": "round3_csv_options",
        "backtestMetadata": {
            "data_dir": str(data_dir),
            "days": sorted(days) if days is not None else "all",
            "mark_mode": mark_mode,
            "timestamp_mode": timestamp_mode,
            "expiry_days_at_start": expiry_days_at_start,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay Round 3 raw CSVs with option-aware valuation.")
    parser.add_argument("algorithm", type=Path, help="Path to the Trader algorithm .py file")
    parser.add_argument("data_dir", type=Path, help="Directory containing prices_round_3_day_*.csv and trades_round_3_day_*.csv")
    parser.add_argument("--out", type=Path, help="Optional path for the generated result JSON")
    parser.add_argument(
        "--day",
        action="append",
        type=int,
        default=[],
        help="Optional day filter; repeat to select multiple days, e.g. --day 0 --day 1",
    )
    parser.add_argument(
        "--mark-mode",
        choices=MARK_MODES,
        default="smile",
        help="How to mark inventory for PnL: mid, conservative, intrinsic, or smile",
    )
    parser.add_argument(
        "--timestamp-mode",
        choices=TIMESTAMP_MODES,
        default="local",
        help="Timestamp exposed to Trader.run: local per day or global across days",
    )
    parser.add_argument(
        "--expiry-days-at-start",
        type=float,
        default=8.0,
        help="TTE at historical day 0 start used by smile/intrinsic marks and exposed observations",
    )
    parser.add_argument(
        "--match-trades",
        choices=("all", "worse", "none"),
        default="all",
        help="How to match remaining orders against the external trade tape",
    )
    parser.add_argument(
        "--default-limit",
        type=int,
        default=80,
        help="Fallback symmetric position limit for products outside the Round 3 defaults",
    )
    parser.add_argument(
        "--limit",
        action="append",
        default=[],
        metavar="PRODUCT=LIMIT",
        help="Override per-product position limit, e.g. --limit VEV_5200=150",
    )
    parser.add_argument(
        "--bootstrap-repetitions",
        type=int,
        default=1000,
        help="Monte Carlo repetitions used for the metrics block; set to 0 to disable",
    )
    parser.add_argument(
        "--bootstrap-block-size",
        type=int,
        default=10,
        help="Block size used for Monte Carlo bootstrap on PnL increments",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=0,
        help="Seed used for Monte Carlo bootstrap on PnL increments",
    )
    args = parser.parse_args(argv)

    selected_days = set(args.day) if args.day else None
    csv_data = load_round3_csv_data(args.data_dir, days=selected_days)
    limits = _round3_limits(csv_data.products, args.default_limit, args.limit)
    artifacts = run_backtest(
        algorithm_path=args.algorithm.expanduser().resolve(),
        csv_data=csv_data,
        limits=limits,
        match_trades=args.match_trades,
        mark_mode=args.mark_mode,
        timestamp_mode=args.timestamp_mode,
        expiry_days_at_start=args.expiry_days_at_start,
    )
    payload = build_output_payload(
        artifacts,
        data_dir=args.data_dir.expanduser().resolve(),
        days=selected_days,
        mark_mode=args.mark_mode,
        timestamp_mode=args.timestamp_mode,
        expiry_days_at_start=args.expiry_days_at_start,
    )
    payload["metrics"] = compute_metrics_from_payload(
        payload,
        source_path=str(args.data_dir.expanduser().resolve()),
        bootstrap_repetitions=args.bootstrap_repetitions,
        bootstrap_block_size=args.bootstrap_block_size,
        bootstrap_seed=args.bootstrap_seed,
    )

    out_path = (
        args.out.expanduser().resolve()
        if args.out
        else Path.cwd() / f"{args.algorithm.stem}.round3csv.backtest.json"
    )
    out_path.write_text(json.dumps(payload, indent=2))

    print(f"Wrote Round 3 CSV replay result to {out_path}")
    print(f"Profit: {artifacts.profit:.4f}")
    print(
        f"Sharpe-like: {payload['metrics']['sharpe_like']:.4f}"
        if payload["metrics"]["sharpe_like"] is not None
        else "Sharpe-like: n/a"
    )
    print(
        f"Max drawdown: {payload['metrics']['max_drawdown']:.4f}"
        if payload["metrics"]["max_drawdown"] is not None
        else "Max drawdown: n/a"
    )
    for position in artifacts.positions:
        print(f"{position['symbol']}: {position['quantity']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
