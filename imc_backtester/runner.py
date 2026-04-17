from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from . import datamodel as compat_datamodel
from .datamodel import Listing, Observation, Order, OrderDepth, Trade, TradingState
from .log_parser import ParsedSubmissionLog, PriceSnapshot, TapeTrade, load_submission_log
from .metrics import compute_metrics_from_payload

ACTIVITIES_HEADER = (
    "day;timestamp;product;bid_price_1;bid_volume_1;bid_price_2;bid_volume_2;"
    "bid_price_3;bid_volume_3;ask_price_1;ask_volume_1;ask_price_2;ask_volume_2;"
    "ask_price_3;ask_volume_3;mid_price;profit_and_loss"
)


@dataclass
class ExternalTrade:
    trade: TapeTrade
    buy_quantity: int
    sell_quantity: int


@dataclass
class BacktestArtifacts:
    activities_log: str
    graph_log: str
    trade_history: list[dict[str, object]]
    logs: list[dict[str, object]]
    positions: list[dict[str, object]]
    profit: float


def parse_limit(values: list[str], products: list[str], default_limit: int) -> dict[str, int]:
    limits = {product: default_limit for product in products}

    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Invalid --limit value '{raw}', expected PRODUCT=LIMIT")

        product, value = raw.split("=", 1)
        limits[product] = int(value)

    return limits


def load_trader_module(algorithm_path: Path):
    if not algorithm_path.is_file():
        raise FileNotFoundError(f"Algorithm file not found: {algorithm_path}")

    module_name = f"imc_user_trader_{algorithm_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, algorithm_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load algorithm module from {algorithm_path}")

    module = importlib.util.module_from_spec(spec)
    package_dir = str(Path(__file__).resolve().parent)
    sys.modules["datamodel"] = compat_datamodel
    sys.path.insert(0, str(algorithm_path.parent))
    sys.path.insert(0, package_dir)

    try:
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == package_dir:
            sys.path.pop(0)
        if sys.path and sys.path[0] == str(algorithm_path.parent):
            sys.path.pop(0)

    if not hasattr(module, "Trader"):
        raise AttributeError(f"{algorithm_path} does not define a Trader class")

    return module


def build_state(log_data: ParsedSubmissionLog, timestamp: int, state: TradingState) -> None:
    state.timestamp = timestamp
    state.listings = {}
    state.order_depths = {}
    state.observations = Observation()

    for product in log_data.products:
        snapshot = log_data.prices[timestamp][product]
        depth = OrderDepth()

        for price, volume in zip(snapshot.bid_prices, snapshot.bid_volumes):
            depth.buy_orders[price] = volume

        for price, volume in zip(snapshot.ask_prices, snapshot.ask_volumes):
            depth.sell_orders[price] = -volume

        state.order_depths[product] = depth
        state.listings[product] = Listing(symbol=product, product=product, denomination="XIRECS")


def normalize_run_output(output):
    orders: dict[str, list[Order]]
    trader_data = ""

    if isinstance(output, tuple):
        if len(output) == 3:
            orders, _conversions, trader_data = output
        elif len(output) == 2:
            orders, trader_data = output
        elif len(output) == 1:
            orders = output[0]
        else:
            raise ValueError(f"Unsupported Trader.run tuple output of length {len(output)}")
    else:
        orders = output

    if not isinstance(orders, dict):
        raise ValueError(f"Trader.run must return a dict or tuple containing a dict, got {type(orders)}")

    normalized: dict[str, list[Order]] = {}
    for product, product_orders in orders.items():
        if not isinstance(product, str):
            raise ValueError(f"Order book key '{product}' is of type {type(product)}, expected str")
        if not isinstance(product_orders, list):
            raise ValueError(f"Orders for '{product}' must be a list")

        normalized_orders: list[Order] = []
        for order in product_orders:
            if not isinstance(order, Order):
                raise ValueError(f"Expected datamodel.Order for '{product}', got {type(order)}")
            if not isinstance(order.price, int) or not isinstance(order.quantity, int):
                raise ValueError(f"Order price and quantity must be ints, got {order}")
            normalized_orders.append(Order(order.symbol, order.price, order.quantity))

        normalized[product] = normalized_orders

    return normalized, str(trader_data)


def enforce_limits(orders: dict[str, list[Order]], position: dict[str, int], limits: dict[str, int]) -> list[str]:
    warnings: list[str] = []

    for product, product_orders in list(orders.items()):
        current_position = position.get(product, 0)
        total_long = sum(order.quantity for order in product_orders if order.quantity > 0)
        total_short = sum(-order.quantity for order in product_orders if order.quantity < 0)
        limit = limits.get(product, 0)

        if current_position + total_long > limit or current_position - total_short < -limit:
            warnings.append(f"Orders for product {product} exceeded limit of {limit}; dropped all orders for this product")
            orders.pop(product, None)

    return warnings


def trade_to_dict(trade: Trade) -> dict[str, object]:
    return {
        "timestamp": trade.timestamp,
        "buyer": trade.buyer,
        "seller": trade.seller,
        "symbol": trade.symbol,
        "currency": "XIRECS",
        "price": float(trade.price),
        "quantity": trade.quantity,
    }


def make_external_trades(tape_trades: list[TapeTrade], submission_trade_mode: str) -> list[ExternalTrade]:
    external_trades: list[ExternalTrade] = []

    for trade in tape_trades:
        if trade.buyer == "SUBMISSION" or trade.seller == "SUBMISSION":
            if submission_trade_mode == "exclude":
                continue

            if submission_trade_mode == "sanitize":
                buy_quantity = 0 if trade.buyer == "SUBMISSION" else trade.quantity
                sell_quantity = 0 if trade.seller == "SUBMISSION" else trade.quantity
                sanitized_buyer = "" if trade.buyer == "SUBMISSION" else trade.buyer
                sanitized_seller = "" if trade.seller == "SUBMISSION" else trade.seller
                sanitized_trade = TapeTrade(
                    timestamp=trade.timestamp,
                    buyer=sanitized_buyer,
                    seller=sanitized_seller,
                    symbol=trade.symbol,
                    currency=trade.currency,
                    price=trade.price,
                    quantity=trade.quantity,
                )
                external_trades.append(
                    ExternalTrade(trade=sanitized_trade, buy_quantity=buy_quantity, sell_quantity=sell_quantity)
                )
                continue

        external_trades.append(ExternalTrade(trade=trade, buy_quantity=trade.quantity, sell_quantity=trade.quantity))

    return external_trades


def match_buy_order(
    order: Order,
    state: TradingState,
    external_trades: list[ExternalTrade],
    realized_cash: dict[str, float],
    match_trades: str,
) -> list[Trade]:
    fills: list[Trade] = []
    depth = state.order_depths[order.symbol]

    for ask_price in sorted(price for price in depth.sell_orders if price <= order.price):
        available = abs(depth.sell_orders[ask_price])
        volume = min(order.quantity, available)
        if volume <= 0:
            continue

        fills.append(Trade(order.symbol, ask_price, volume, "SUBMISSION", "", state.timestamp))
        state.position[order.symbol] = state.position.get(order.symbol, 0) + volume
        realized_cash[order.symbol] = realized_cash.get(order.symbol, 0.0) - ask_price * volume
        depth.sell_orders[ask_price] += volume
        if depth.sell_orders[ask_price] == 0:
            depth.sell_orders.pop(ask_price)
        order.quantity -= volume
        if order.quantity == 0:
            return fills

    if match_trades == "none":
        return fills

    for tape_trade in external_trades:
        if tape_trade.sell_quantity == 0:
            continue
        if tape_trade.trade.price > order.price:
            continue
        if tape_trade.trade.price == order.price and match_trades == "worse":
            continue

        volume = min(order.quantity, tape_trade.sell_quantity)
        if volume <= 0:
            continue

        fills.append(Trade(order.symbol, order.price, volume, "SUBMISSION", tape_trade.trade.seller, state.timestamp))
        state.position[order.symbol] = state.position.get(order.symbol, 0) + volume
        realized_cash[order.symbol] = realized_cash.get(order.symbol, 0.0) - order.price * volume
        tape_trade.sell_quantity -= volume
        order.quantity -= volume
        if order.quantity == 0:
            return fills

    return fills


def match_sell_order(
    order: Order,
    state: TradingState,
    external_trades: list[ExternalTrade],
    realized_cash: dict[str, float],
    match_trades: str,
) -> list[Trade]:
    fills: list[Trade] = []
    depth = state.order_depths[order.symbol]

    for bid_price in sorted((price for price in depth.buy_orders if price >= order.price), reverse=True):
        available = depth.buy_orders[bid_price]
        volume = min(-order.quantity, available)
        if volume <= 0:
            continue

        fills.append(Trade(order.symbol, bid_price, volume, "", "SUBMISSION", state.timestamp))
        state.position[order.symbol] = state.position.get(order.symbol, 0) - volume
        realized_cash[order.symbol] = realized_cash.get(order.symbol, 0.0) + bid_price * volume
        depth.buy_orders[bid_price] -= volume
        if depth.buy_orders[bid_price] == 0:
            depth.buy_orders.pop(bid_price)
        order.quantity += volume
        if order.quantity == 0:
            return fills

    if match_trades == "none":
        return fills

    for tape_trade in external_trades:
        if tape_trade.buy_quantity == 0:
            continue
        if tape_trade.trade.price < order.price:
            continue
        if tape_trade.trade.price == order.price and match_trades == "worse":
            continue

        volume = min(-order.quantity, tape_trade.buy_quantity)
        if volume <= 0:
            continue

        fills.append(Trade(order.symbol, order.price, volume, tape_trade.trade.buyer, "SUBMISSION", state.timestamp))
        state.position[order.symbol] = state.position.get(order.symbol, 0) - volume
        realized_cash[order.symbol] = realized_cash.get(order.symbol, 0.0) + order.price * volume
        tape_trade.buy_quantity -= volume
        order.quantity += volume
        if order.quantity == 0:
            return fills

    return fills


def match_orders_for_product(
    product: str,
    product_orders: list[Order],
    state: TradingState,
    tape_trades: list[TapeTrade],
    realized_cash: dict[str, float],
    match_trades: str,
    submission_trade_mode: str,
) -> tuple[list[Trade], list[Trade]]:
    fills: list[Trade] = []
    external_trades = make_external_trades(tape_trades, submission_trade_mode)

    for order in product_orders:
        working_order = Order(order.symbol, order.price, order.quantity)
        if working_order.quantity > 0:
            fills.extend(match_buy_order(working_order, state, external_trades, realized_cash, match_trades))
        elif working_order.quantity < 0:
            fills.extend(match_sell_order(working_order, state, external_trades, realized_cash, match_trades))

    remaining_market_trades: list[Trade] = []
    for external in external_trades:
        remaining_quantity = min(external.buy_quantity, external.sell_quantity)
        if remaining_quantity <= 0:
            continue
        remaining_market_trades.append(
            Trade(
                symbol=external.trade.symbol,
                price=external.trade.price,
                quantity=remaining_quantity,
                buyer=external.trade.buyer,
                seller=external.trade.seller,
                timestamp=external.trade.timestamp,
            )
        )

    fills.sort(key=lambda trade: (trade.timestamp, trade.symbol, trade.price, trade.quantity))
    remaining_market_trades.sort(key=lambda trade: (trade.timestamp, trade.symbol, trade.price, trade.quantity))
    return fills, remaining_market_trades


def format_activity_row(snapshot: PriceSnapshot, profit: float) -> str:
    columns = [
        snapshot.day,
        snapshot.timestamp,
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


def resolve_mark_price(snapshot: PriceSnapshot, previous_mark_price: float) -> float:
    if snapshot.mid_price > 0:
        return snapshot.mid_price

    if snapshot.bid_prices and snapshot.ask_prices:
        return (snapshot.bid_prices[0] + snapshot.ask_prices[0]) / 2

    return previous_mark_price


def run_backtest(
    algorithm_path: Path,
    log_path: Path,
    limits: dict[str, int],
    match_trades: str,
    submission_trade_mode: str,
) -> BacktestArtifacts:
    log_data = load_submission_log(log_path, include_submission_trades=True)
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

    realized_cash = {product: 0.0 for product in log_data.products}
    mark_prices = {product: 0.0 for product in log_data.products}
    logs: list[dict[str, object]] = []
    activities_rows = [ACTIVITIES_HEADER]
    graph_points = ["timestamp;value"]
    output_trades: list[dict[str, object]] = []

    for timestamp in log_data.timestamps:
        build_state(log_data, timestamp, state)
        stdout = StringIO()

        with redirect_stdout(stdout):
            raw_output = trader.run(state)

        orders, trader_data = normalize_run_output(raw_output)
        sandbox_messages = enforce_limits(orders, state.position, limits)
        log_row = {
            "sandboxLog": "\n".join(sandbox_messages),
            "lambdaLog": stdout.getvalue().rstrip(),
            "timestamp": timestamp,
        }
        logs.append(log_row)

        current_market_trades: dict[str, list[Trade]] = {}
        current_own_trades: dict[str, list[Trade]] = {}

        for product in log_data.products:
            fills, remaining_market_trades = match_orders_for_product(
                product=product,
                product_orders=orders.get(product, []),
                state=state,
                tape_trades=log_data.trade_history.get(timestamp, {}).get(product, []),
                realized_cash=realized_cash,
                match_trades=match_trades,
                submission_trade_mode=submission_trade_mode,
            )

            if fills:
                current_own_trades[product] = fills
                output_trades.extend(trade_to_dict(fill) for fill in fills)

            if remaining_market_trades:
                current_market_trades[product] = remaining_market_trades
                output_trades.extend(trade_to_dict(trade) for trade in remaining_market_trades)

        state.own_trades = current_own_trades
        state.market_trades = current_market_trades
        state.traderData = trader_data

        total_profit = 0.0
        for product in log_data.products:
            snapshot = log_data.prices[timestamp][product]
            mark_prices[product] = resolve_mark_price(snapshot, mark_prices[product])
            marked_profit = realized_cash[product] + state.position.get(product, 0) * mark_prices[product]
            activities_rows.append(format_activity_row(snapshot, marked_profit))
            total_profit += marked_profit

        graph_points.append(f"{timestamp};{total_profit}")

    positions = [
        {"symbol": "XIRECS", "quantity": int(sum(realized_cash.values()))},
        *(
            {"symbol": product, "quantity": state.position.get(product, 0)}
            for product in log_data.products
        ),
    ]
    final_profit = float(sum(realized_cash[product] + state.position.get(product, 0) * mark_prices[product] for product in log_data.products))

    output_trades.sort(key=lambda trade: (int(trade["timestamp"]), str(trade["symbol"]), float(trade["price"]), int(trade["quantity"])))

    return BacktestArtifacts(
        activities_log="\n".join(activities_rows),
        graph_log="\n".join(graph_points),
        trade_history=output_trades,
        logs=logs,
        positions=positions,
        profit=final_profit,
    )


def build_output_payload(artifacts: BacktestArtifacts) -> dict[str, object]:
    return {
        "round": "local",
        "status": "FINISHED",
        "profit": artifacts.profit,
        "activitiesLog": artifacts.activities_log,
        "graphLog": artifacts.graph_log,
        "tradeHistory": artifacts.trade_history,
        "logs": artifacts.logs,
        "positions": artifacts.positions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay current IMC submission logs against a local Trader.")
    parser.add_argument("algorithm", type=Path, help="Path to the Trader algorithm .py file")
    parser.add_argument("log_file", type=Path, help="Path to the downloaded IMC .log JSON file")
    parser.add_argument("--out", type=Path, help="Optional path for the generated result JSON")
    parser.add_argument(
        "--match-trades",
        choices=("all", "worse", "none"),
        default="all",
        help="How to match remaining orders against external trade tape",
    )
    parser.add_argument(
        "--default-limit",
        type=int,
        default=80,
        help="Default symmetric position limit applied to products not listed in --limit",
    )
    parser.add_argument(
        "--limit",
        action="append",
        default=[],
        metavar="PRODUCT=LIMIT",
        help="Override per-product position limit, e.g. --limit ASH_COATED_OSMIUM=80",
    )
    parser.add_argument(
        "--submission-trades",
        choices=("sanitize", "full", "exclude"),
        default="sanitize",
        help="How to treat SUBMISSION rows already present in the downloaded trade history",
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

    log_data = load_submission_log(args.log_file, include_submission_trades=True)
    limits = parse_limit(args.limit, log_data.products, args.default_limit)
    artifacts = run_backtest(
        algorithm_path=args.algorithm.expanduser().resolve(),
        log_path=args.log_file.expanduser().resolve(),
        limits=limits,
        match_trades=args.match_trades,
        submission_trade_mode=args.submission_trades,
    )
    payload = build_output_payload(artifacts)
    payload["metrics"] = compute_metrics_from_payload(
        payload,
        source_path=str(args.log_file.expanduser().resolve()),
        bootstrap_repetitions=args.bootstrap_repetitions,
        bootstrap_block_size=args.bootstrap_block_size,
        bootstrap_seed=args.bootstrap_seed,
    )

    out_path = args.out.expanduser().resolve() if args.out else Path.cwd() / f"{args.algorithm.stem}.backtest.json"
    out_path.write_text(json.dumps(payload, indent=2))

    print(f"Wrote replay result to {out_path}")
    print(f"Profit: {artifacts.profit:.4f}")
    print(f"Sharpe-like: {payload['metrics']['sharpe_like']:.4f}" if payload["metrics"]["sharpe_like"] is not None else "Sharpe-like: n/a")
    print(f"Max drawdown: {payload['metrics']['max_drawdown']:.4f}" if payload["metrics"]["max_drawdown"] is not None else "Max drawdown: n/a")
    for position in artifacts.positions:
        print(f"{position['symbol']}: {position['quantity']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
