from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


ROOT = Path("ROUND1")
PRICE_FILES = sorted(ROOT.glob("prices_round_1_day_*.csv"))
TRADE_FILES = sorted(ROOT.glob("trades_round_1_day_*.csv"))

PRODUCTS = ("ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT")
POSITION_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}


@dataclass(frozen=True)
class ACOParams:
    fair_value: float
    take_edge: float
    quote_edge: float
    inventory_skew: float
    quote_size: int


@dataclass(frozen=True)
class IPRParams:
    drift_per_timestamp: float
    microprice_weight: float
    take_edge: float
    bid_quote_edge: float
    ask_quote_edge: float
    inventory_skew: float
    quote_size: int


@dataclass
class DayBook:
    product: str
    day: int
    timestamp: np.ndarray
    bid: np.ndarray
    ask: np.ndarray
    bid_volume: np.ndarray
    ask_volume: np.ndarray
    micro_dev: np.ndarray
    next_bid: np.ndarray
    next_ask: np.ndarray
    next_mid: np.ndarray
    interval_trades: List[List[Tuple[int, int]]]
    last_mid: float


def load_prices() -> pd.DataFrame:
    prices = pd.concat([pd.read_csv(path, sep=";") for path in PRICE_FILES], ignore_index=True)
    for column in prices.columns:
        if column != "product":
            prices[column] = pd.to_numeric(prices[column], errors="coerce")

    prices["has_top_book"] = (
        prices["bid_price_1"].notna()
        & prices["ask_price_1"].notna()
        & (prices["bid_price_1"] > 0)
        & (prices["ask_price_1"] > 0)
    )
    prices = prices[prices["has_top_book"]].copy()
    prices["mid"] = (prices["bid_price_1"] + prices["ask_price_1"]) / 2.0

    total = (
        prices["bid_volume_1"].fillna(0) + prices["ask_volume_1"].fillna(0)
    ).replace(0, np.nan)
    prices["microprice"] = (
        prices["ask_price_1"] * prices["bid_volume_1"].fillna(0)
        + prices["bid_price_1"] * prices["ask_volume_1"].fillna(0)
    ) / total
    prices["micro_dev"] = prices["microprice"].fillna(prices["mid"]) - prices["mid"]
    return prices.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)


def load_trades() -> pd.DataFrame:
    trades = []
    for path in TRADE_FILES:
        frame = pd.read_csv(path, sep=";")
        frame["day"] = int(path.stem.split("_")[-1])
        trades.append(frame)

    all_trades = pd.concat(trades, ignore_index=True)
    all_trades["timestamp"] = pd.to_numeric(all_trades["timestamp"], errors="coerce")
    all_trades["price"] = pd.to_numeric(all_trades["price"], errors="coerce")
    all_trades["quantity"] = pd.to_numeric(all_trades["quantity"], errors="coerce")
    all_trades = all_trades.dropna(subset=["timestamp", "price", "quantity"])
    return all_trades


def build_day_books(prices: pd.DataFrame, trades: pd.DataFrame) -> Dict[str, List[DayBook]]:
    books: Dict[str, List[DayBook]] = {product: [] for product in PRODUCTS}
    trade_map: Dict[Tuple[str, int, int], List[Tuple[int, int]]] = {}

    grouped_trades = trades.groupby(["symbol", "day", "timestamp"])
    for (symbol, day, timestamp), frame in grouped_trades:
        trade_map[(symbol, int(day), int(timestamp))] = [
            (int(price), int(quantity))
            for price, quantity in zip(frame["price"], frame["quantity"])
        ]

    for product in PRODUCTS:
        product_prices = prices[prices["product"] == product].copy()
        for day, frame in product_prices.groupby("day"):
            frame = frame.sort_values("timestamp").reset_index(drop=True)
            next_bid = frame["bid_price_1"].shift(-1).to_numpy()
            next_ask = frame["ask_price_1"].shift(-1).to_numpy()
            next_mid = frame["mid"].shift(-1).to_numpy()

            interval_trades: List[List[Tuple[int, int]]] = []
            timestamps = frame["timestamp"].to_numpy(dtype=int)
            for index, timestamp in enumerate(timestamps):
                if index + 1 >= len(timestamps):
                    interval_trades.append([])
                    continue
                next_timestamp = int(timestamps[index + 1])
                interval_trades.append(
                    trade_map.get((product, int(day), next_timestamp), [])
                )

            books[product].append(
                DayBook(
                    product=product,
                    day=int(day),
                    timestamp=timestamps,
                    bid=frame["bid_price_1"].to_numpy(dtype=int),
                    ask=frame["ask_price_1"].to_numpy(dtype=int),
                    bid_volume=frame["bid_volume_1"].to_numpy(dtype=int),
                    ask_volume=frame["ask_volume_1"].to_numpy(dtype=int),
                    micro_dev=frame["micro_dev"].to_numpy(dtype=float),
                    next_bid=np.nan_to_num(next_bid, nan=-1).astype(int),
                    next_ask=np.nan_to_num(next_ask, nan=-1).astype(int),
                    next_mid=np.nan_to_num(next_mid, nan=np.nan),
                    interval_trades=interval_trades,
                    last_mid=float(frame["mid"].iloc[-1]),
                )
            )

    return books


def passive_buy_fill(
    price: int,
    quantity: int,
    current_bid: int,
    next_ask: int,
    trades: List[Tuple[int, int]],
) -> int:
    if quantity <= 0:
        return 0
    if next_ask > 0 and next_ask <= price:
        return quantity

    traded_volume = sum(trade_qty for trade_price, trade_qty in trades if trade_price <= price)
    if traded_volume <= 0:
        return 0

    queue_factor = 1.0 if price > current_bid else 0.35
    return min(quantity, int(math.floor(traded_volume * queue_factor)))


def passive_sell_fill(
    price: int,
    quantity: int,
    current_ask: int,
    next_bid: int,
    trades: List[Tuple[int, int]],
) -> int:
    if quantity <= 0:
        return 0
    if next_bid > 0 and next_bid >= price:
        return quantity

    traded_volume = sum(trade_qty for trade_price, trade_qty in trades if trade_price >= price)
    if traded_volume <= 0:
        return 0

    queue_factor = 1.0 if price < current_ask else 0.35
    return min(quantity, int(math.floor(traded_volume * queue_factor)))


def ipr_bid_size(position: int, limit: int, quote_size: int) -> int:
    remaining = limit - position
    if remaining <= 0:
        return 0
    if position >= limit - 10:
        return min(2, remaining)
    if position >= limit - 20:
        return min(4, remaining)
    return min(quote_size, remaining)


def ipr_ask_size(position: int, quote_size: int) -> int:
    if position <= 0:
        return 0
    if position >= 35:
        return max(quote_size, 12)
    if position >= 20:
        return max(quote_size, 10)
    return quote_size


def simulate_aco_day(day_book: DayBook, params: ACOParams) -> Tuple[float, float]:
    limit = POSITION_LIMITS["ASH_COATED_OSMIUM"]
    position = 0
    cash = 0.0
    lower_cash = 0.0
    lower_position = 0

    for i in range(len(day_book.timestamp)):
        bid = int(day_book.bid[i])
        ask = int(day_book.ask[i])
        bid_volume = int(day_book.bid_volume[i])
        ask_volume = int(day_book.ask_volume[i])
        trades = day_book.interval_trades[i]

        reservation = params.fair_value - position * params.inventory_skew
        lower_reservation = params.fair_value - lower_position * params.inventory_skew

        if ask <= reservation - params.take_edge and position < limit:
            quantity = min(ask_volume, limit - position)
            if quantity > 0:
                cash -= quantity * ask
                position += quantity

        if bid >= reservation + params.take_edge and position > -limit:
            quantity = min(bid_volume, position + limit)
            if quantity > 0:
                cash += quantity * bid
                position -= quantity

        if ask <= lower_reservation - params.take_edge and lower_position < limit:
            quantity = min(ask_volume, limit - lower_position)
            if quantity > 0:
                lower_cash -= quantity * ask
                lower_position += quantity

        if bid >= lower_reservation + params.take_edge and lower_position > -limit:
            quantity = min(bid_volume, lower_position + limit)
            if quantity > 0:
                lower_cash += quantity * bid
                lower_position -= quantity

        bid_quote = min(bid + 1, math.floor(reservation - params.quote_edge))
        ask_quote = max(ask - 1, math.ceil(reservation + params.quote_edge))

        bid_size = min(params.quote_size, limit - position)
        if bid_size > 0 and bid_quote > 0 and bid_quote < ask:
            filled = passive_buy_fill(
                bid_quote,
                bid_size,
                bid,
                int(day_book.next_ask[i]),
                trades,
            )
            if filled > 0:
                cash -= filled * bid_quote
                position += filled

        ask_size = min(params.quote_size, limit + position)
        if ask_size > 0 and ask_quote > bid:
            filled = passive_sell_fill(
                ask_quote,
                ask_size,
                ask,
                int(day_book.next_bid[i]),
                trades,
            )
            if filled > 0:
                cash += filled * ask_quote
                position -= filled

    pnl = cash + position * day_book.last_mid
    lower_pnl = lower_cash + lower_position * day_book.last_mid
    return pnl, lower_pnl


def simulate_ipr_day(day_book: DayBook, params: IPRParams) -> Tuple[float, float]:
    limit = POSITION_LIMITS["INTARIAN_PEPPER_ROOT"]
    position = 0
    cash = 0.0
    lower_cash = 0.0
    lower_position = 0

    day_open_mid = (day_book.bid[0] + day_book.ask[0]) / 2.0
    day_open_timestamp = int(day_book.timestamp[0])

    for i in range(len(day_book.timestamp)):
        timestamp = int(day_book.timestamp[i])
        bid = int(day_book.bid[i])
        ask = int(day_book.ask[i])
        bid_volume = int(day_book.bid_volume[i])
        ask_volume = int(day_book.ask_volume[i])
        micro_dev = float(day_book.micro_dev[i])
        trades = day_book.interval_trades[i]

        trend_fair = day_open_mid + params.drift_per_timestamp * (timestamp - day_open_timestamp)
        fair_value = trend_fair + params.microprice_weight * micro_dev

        reservation = fair_value - position * params.inventory_skew
        lower_reservation = fair_value - lower_position * params.inventory_skew

        if ask <= fair_value - params.take_edge and position < limit:
            quantity = min(ask_volume, limit - position)
            if quantity > 0:
                cash -= quantity * ask
                position += quantity

        if position > 0 and bid >= fair_value + params.take_edge:
            quantity = min(bid_volume, position + limit)
            if quantity > 0:
                cash += quantity * bid
                position -= quantity

        if ask <= fair_value - params.take_edge and lower_position < limit:
            quantity = min(ask_volume, limit - lower_position)
            if quantity > 0:
                lower_cash -= quantity * ask
                lower_position += quantity

        if lower_position > 0 and bid >= fair_value + params.take_edge:
            quantity = min(bid_volume, lower_position + limit)
            if quantity > 0:
                lower_cash += quantity * bid
                lower_position -= quantity

        bid_quote = min(bid + 1, math.floor(reservation - params.bid_quote_edge))
        bid_size = ipr_bid_size(position, limit, params.quote_size)
        if bid_size > 0 and bid_quote > 0 and bid_quote < ask:
            filled = passive_buy_fill(
                bid_quote,
                bid_size,
                bid,
                int(day_book.next_ask[i]),
                trades,
            )
            if filled > 0:
                cash -= filled * bid_quote
                position += filled

        if position > 0:
            ask_quote = max(ask - 1, math.ceil(reservation + params.ask_quote_edge))
            ask_size = min(ipr_ask_size(position, params.quote_size), limit + position)
            if ask_size > 0 and ask_quote > bid:
                filled = passive_sell_fill(
                    ask_quote,
                    ask_size,
                    ask,
                    int(day_book.next_bid[i]),
                    trades,
                )
                if filled > 0:
                    cash += filled * ask_quote
                    position -= filled

    pnl = cash + position * day_book.last_mid
    lower_pnl = lower_cash + lower_position * day_book.last_mid
    return pnl, lower_pnl


def evaluate_aco(books: Iterable[DayBook], params: ACOParams) -> Dict:
    pnls = []
    lower_pnls = []
    for day_book in books:
        pnl, lower_pnl = simulate_aco_day(day_book, params)
        pnls.append(pnl)
        lower_pnls.append(lower_pnl)
    return summarize_result(params, pnls, lower_pnls)


def evaluate_ipr(books: Iterable[DayBook], params: IPRParams) -> Dict:
    pnls = []
    lower_pnls = []
    for day_book in books:
        pnl, lower_pnl = simulate_ipr_day(day_book, params)
        pnls.append(pnl)
        lower_pnls.append(lower_pnl)
    return summarize_result(params, pnls, lower_pnls)


def summarize_result(params, pnls: List[float], lower_pnls: List[float]) -> Dict:
    mean_pnl = float(np.mean(pnls))
    std_pnl = float(np.std(pnls))
    total_pnl = float(np.sum(pnls))
    total_lower = float(np.sum(lower_pnls))
    min_day = float(np.min(pnls))

    # Prefer parameter sets that make money in the passive-fill replay and do not
    # collapse under the aggressive-only lower bound.
    score = total_pnl + 0.35 * total_lower - 0.75 * std_pnl + 0.25 * min_day
    return {
        "params": params,
        "score": score,
        "total_pnl": total_pnl,
        "total_lower": total_lower,
        "day_pnls": tuple(round(pnl, 1) for pnl in pnls),
        "day_lower": tuple(round(pnl, 1) for pnl in lower_pnls),
    }


def aco_candidates() -> Iterable[ACOParams]:
    for take_edge, quote_edge, inventory_skew, quote_size in product(
        [0.5, 1.0, 1.5, 2.0],
        [3.0, 4.0, 5.0, 6.0],
        [0.05, 0.10, 0.15, 0.20],
        [8, 10, 12, 14],
    ):
        yield ACOParams(
            fair_value=10000.0,
            take_edge=take_edge,
            quote_edge=quote_edge,
            inventory_skew=inventory_skew,
            quote_size=quote_size,
        )


def sample_ipr_candidates(count: int, seed: int) -> List[IPRParams]:
    rng = random.Random(seed)
    candidates = set()

    while len(candidates) < count:
        params = IPRParams(
            drift_per_timestamp=rng.choice([0.00085, 0.0009, 0.00095, 0.0010, 0.00105, 0.0011, 0.00115, 0.0012]),
            microprice_weight=rng.choice([0.5, 1.0, 1.5, 2.0, 2.5]),
            take_edge=rng.choice([2.0, 2.5, 3.0, 3.5, 4.0, 4.5]),
            bid_quote_edge=rng.choice([3.0, 3.5, 4.0, 4.5, 5.0, 5.5]),
            ask_quote_edge=rng.choice([4.0, 5.0, 6.0, 7.0, 8.0]),
            inventory_skew=rng.choice([0.04, 0.08, 0.12, 0.16, 0.20]),
            quote_size=rng.choice([4, 6, 8, 10]),
        )
        candidates.add(params)

    return list(candidates)


def local_ipr_neighborhood(base: IPRParams) -> List[IPRParams]:
    neighborhood = {base}

    def add_variant(**updates: float | int) -> None:
        params = IPRParams(
            drift_per_timestamp=round(updates.get("drift_per_timestamp", base.drift_per_timestamp), 8),
            microprice_weight=round(updates.get("microprice_weight", base.microprice_weight), 4),
            take_edge=round(updates.get("take_edge", base.take_edge), 4),
            bid_quote_edge=round(updates.get("bid_quote_edge", base.bid_quote_edge), 4),
            ask_quote_edge=round(updates.get("ask_quote_edge", base.ask_quote_edge), 4),
            inventory_skew=round(updates.get("inventory_skew", base.inventory_skew), 4),
            quote_size=int(updates.get("quote_size", base.quote_size)),
        )
        if (
            params.drift_per_timestamp >= 0.0
            and params.microprice_weight >= 0.0
            and params.take_edge >= 0.5
            and params.bid_quote_edge >= 1.0
            and params.ask_quote_edge >= params.bid_quote_edge
            and params.inventory_skew >= 0.0
            and params.quote_size >= 2
        ):
            neighborhood.add(params)

    for delta in (-0.0001, -0.00005, 0.00005, 0.0001):
        add_variant(drift_per_timestamp=base.drift_per_timestamp + delta)
    for delta in (-0.5, 0.5):
        add_variant(microprice_weight=base.microprice_weight + delta)
        add_variant(take_edge=base.take_edge + delta)
        add_variant(bid_quote_edge=base.bid_quote_edge + delta)
        add_variant(inventory_skew=base.inventory_skew + (0.08 * np.sign(delta)))
    for delta in (-1.0, 1.0):
        add_variant(ask_quote_edge=base.ask_quote_edge + delta)
    for delta in (-2, 2):
        add_variant(quote_size=base.quote_size + delta)

    return list(neighborhood)


def print_top_results(name: str, results: List[Dict], top_n: int = 5) -> None:
    print(f"\n{name} top {min(top_n, len(results))} candidates")
    for index, result in enumerate(results[:top_n], start=1):
        print(
            f"{index}. score={result['score']:.1f} total_pnl={result['total_pnl']:.1f} "
            f"lower={result['total_lower']:.1f} day_pnls={result['day_pnls']} params={result['params']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Round 1 strategy parameters on local historical data.")
    parser.add_argument("--ipr-samples", type=int, default=400, help="Number of coarse random IPR candidates.")
    parser.add_argument("--ipr-topk", type=int, default=12, help="How many coarse IPR candidates to refine.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for IPR candidate sampling.")
    args = parser.parse_args()

    prices = load_prices()
    trades = load_trades()
    books = build_day_books(prices, trades)

    aco_results = [evaluate_aco(books["ASH_COATED_OSMIUM"], params) for params in aco_candidates()]
    aco_results.sort(key=lambda result: result["score"], reverse=True)
    best_aco = aco_results[0]
    print_top_results("ACO", aco_results)

    coarse_ipr_candidates = sample_ipr_candidates(args.ipr_samples, args.seed)
    coarse_ipr_results = [evaluate_ipr(books["INTARIAN_PEPPER_ROOT"], params) for params in coarse_ipr_candidates]
    coarse_ipr_results.sort(key=lambda result: result["score"], reverse=True)
    print_top_results("IPR coarse", coarse_ipr_results)

    refined_candidates = set()
    for coarse_result in coarse_ipr_results[: args.ipr_topk]:
        refined_candidates.update(local_ipr_neighborhood(coarse_result["params"]))

    refined_ipr_results = [evaluate_ipr(books["INTARIAN_PEPPER_ROOT"], params) for params in refined_candidates]
    refined_ipr_results.sort(key=lambda result: result["score"], reverse=True)
    best_ipr = refined_ipr_results[0]
    print_top_results("IPR refined", refined_ipr_results)

    print("\nBest parameters to copy into the strategy")
    print("ACO", best_aco["params"])
    print("IPR", best_ipr["params"])


if __name__ == "__main__":
    main()
