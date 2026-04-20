from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


ROOT = Path("ROUND1")
PRICE_FILES = sorted(ROOT.glob("prices_round_1_day_*.csv"))
TRADE_FILES = sorted(ROOT.glob("trades_round_1_day_*.csv"))

PRODUCTS = ("ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT")
POSITION_LIMITS = {
    "ASH_COATED_OSMIUM": 50,
    "INTARIAN_PEPPER_ROOT": 50,
}

ACO_GRID = {
    "take_edge": [0.5, 1.0, 1.5],
    "quote_edge": [2.5, 3.0, 3.5, 4.0],
    "inventory_skew": [0.10, 0.15, 0.20, 0.25],
    "quote_size": [10, 12, 14],
    "microprice_weight": [0.0, 0.5, 1.0],
    "ofi_weight": [0.0, 0.5, 1.0, 1.5],
    "stale_decay": [0.15, 0.25, 0.35, 0.45],
    "stale_widen": [0.5, 0.8, 1.1, 1.4],
    "stale_halt_steps": [2, 3, 4, 5],
}

IPR_GRID = {
    "drift_per_timestamp": [0.0010, 0.0011, 0.0012, 0.00125, 0.0013, 0.00135],
    "take_edge": [2.0, 2.5, 3.0, 3.5, 4.0],
    "bid_quote_edge": [3.0, 3.5, 4.0, 4.5],
    "ask_quote_edge": [5.0, 5.5, 6.0, 7.0],
    "inventory_skew": [0.08, 0.12, 0.16, 0.20],
    "quote_size": [6, 8, 10],
    "microprice_weight": [1.0, 1.5, 2.0, 2.5, 3.0],
    "ofi_weight": [0.5, 1.0, 1.5, 2.0, 2.5],
    "stale_decay": [0.10, 0.15, 0.20, 0.25, 0.30],
    "stale_widen": [0.5, 0.8, 1.1, 1.4],
    "stale_halt_steps": [2, 3, 4, 5],
}


@dataclass(frozen=True)
class ACOFreshParams:
    fair_value: float
    take_edge: float
    quote_edge: float
    inventory_skew: float
    quote_size: int
    microprice_weight: float
    ofi_weight: float
    stale_decay: float
    stale_widen: float
    stale_halt_steps: int


@dataclass(frozen=True)
class IPRFreshParams:
    drift_per_timestamp: float
    take_edge: float
    bid_quote_edge: float
    ask_quote_edge: float
    inventory_skew: float
    quote_size: int
    microprice_weight: float
    ofi_weight: float
    stale_decay: float
    stale_widen: float
    stale_halt_steps: int


@dataclass
class RawDayBook:
    product: str
    day: int
    timestamp: np.ndarray
    valid: np.ndarray
    bid: np.ndarray
    ask: np.ndarray
    bid_volume: np.ndarray
    ask_volume: np.ndarray
    micro_dev: np.ndarray
    next_bid: np.ndarray
    next_ask: np.ndarray
    interval_trades: List[List[Tuple[int, int]]]
    last_valid_mid: float


def load_prices() -> pd.DataFrame:
    prices = pd.concat([pd.read_csv(path, sep=";") for path in PRICE_FILES], ignore_index=True)
    for column in prices.columns:
        if column != "product":
            prices[column] = pd.to_numeric(prices[column], errors="coerce")

    prices["valid"] = (
        prices["bid_price_1"].notna()
        & prices["ask_price_1"].notna()
        & (prices["bid_price_1"] > 0)
        & (prices["ask_price_1"] > 0)
        & (prices["bid_volume_1"] > 0)
        & (prices["ask_volume_1"] > 0)
        & (prices["bid_price_1"] < prices["ask_price_1"])
    )

    valid_total = (
        prices["bid_volume_1"].fillna(0) + prices["ask_volume_1"].fillna(0)
    ).replace(0, np.nan)
    valid_micro = (
        prices["ask_price_1"] * prices["bid_volume_1"].fillna(0)
        + prices["bid_price_1"] * prices["ask_volume_1"].fillna(0)
    ) / valid_total
    valid_mid = (prices["bid_price_1"] + prices["ask_price_1"]) / 2.0
    prices["micro_dev"] = np.where(prices["valid"], valid_micro - valid_mid, 0.0)
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


def build_day_books(prices: pd.DataFrame, trades: pd.DataFrame) -> Dict[str, List[RawDayBook]]:
    books: Dict[str, List[RawDayBook]] = {product: [] for product in PRODUCTS}
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
            timestamps = frame["timestamp"].to_numpy(dtype=int)
            valid = frame["valid"].to_numpy(dtype=bool)

            next_bid = np.full(len(frame), -1, dtype=int)
            next_ask = np.full(len(frame), -1, dtype=int)
            interval_trades: List[List[Tuple[int, int]]] = []

            for index, timestamp in enumerate(timestamps):
                if index + 1 < len(frame):
                    next_bid[index] = int(frame["bid_price_1"].iloc[index + 1]) if bool(frame["valid"].iloc[index + 1]) else -1
                    next_ask[index] = int(frame["ask_price_1"].iloc[index + 1]) if bool(frame["valid"].iloc[index + 1]) else -1
                    interval_trades.append(
                        trade_map.get((product, int(day), int(timestamps[index + 1])), [])
                    )
                else:
                    interval_trades.append([])

            valid_rows = frame[frame["valid"]]
            last_valid_mid = float(
                ((valid_rows["bid_price_1"] + valid_rows["ask_price_1"]) / 2.0).iloc[-1]
            )

            books[product].append(
                RawDayBook(
                    product=product,
                    day=int(day),
                    timestamp=timestamps,
                    valid=valid,
                    bid=np.where(valid, frame["bid_price_1"], -1).astype(int),
                    ask=np.where(valid, frame["ask_price_1"], -1).astype(int),
                    bid_volume=np.where(valid, frame["bid_volume_1"], 0).astype(int),
                    ask_volume=np.where(valid, frame["ask_volume_1"], 0).astype(int),
                    micro_dev=frame["micro_dev"].to_numpy(dtype=float),
                    next_bid=next_bid,
                    next_ask=next_ask,
                    interval_trades=interval_trades,
                    last_valid_mid=last_valid_mid,
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


def stale_steps(timestamp: int, last_valid_timestamp: int | None) -> int:
    if last_valid_timestamp is None:
        return 0
    return max(0, (timestamp - last_valid_timestamp) // 100 - 1)


def normalized_ofi(
    bid: int,
    bid_volume: int,
    ask: int,
    ask_volume: int,
    last_book: Tuple[int, int, int, int] | None,
) -> float:
    if last_book is None:
        return 0.0

    prev_bid, prev_bid_volume, prev_ask, prev_ask_volume = last_book
    ofi = 0.0

    if bid > prev_bid:
        ofi += bid_volume
    elif bid == prev_bid:
        ofi += bid_volume - prev_bid_volume
    else:
        ofi -= prev_bid_volume

    if ask < prev_ask:
        ofi += prev_ask_volume
    elif ask == prev_ask:
        ofi += prev_ask_volume - ask_volume
    else:
        ofi -= ask_volume

    scale = max(
        1.0,
        (bid_volume + ask_volume + prev_bid_volume + prev_ask_volume) / 2.0,
    )
    return ofi / scale


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


def simulate_aco_day(day_book: RawDayBook, params: ACOFreshParams) -> Tuple[float, float]:
    limit = POSITION_LIMITS["ASH_COATED_OSMIUM"]
    cash = 0.0
    position = 0
    lower_cash = 0.0
    lower_position = 0
    last_valid_timestamp: int | None = None
    last_book: Tuple[int, int, int, int] | None = None

    for i in range(len(day_book.timestamp)):
        timestamp = int(day_book.timestamp[i])
        if not bool(day_book.valid[i]):
            continue

        bid = int(day_book.bid[i])
        ask = int(day_book.ask[i])
        bid_volume = int(day_book.bid_volume[i])
        ask_volume = int(day_book.ask_volume[i])
        micro_dev = float(day_book.micro_dev[i])
        trades = day_book.interval_trades[i]

        stale = stale_steps(timestamp, last_valid_timestamp)
        freshness = math.exp(-params.stale_decay * stale)
        ofi = normalized_ofi(bid, bid_volume, ask, ask_volume, last_book)
        signal = freshness * (params.microprice_weight * micro_dev + params.ofi_weight * ofi)

        fair = params.fair_value + signal
        reservation = fair - position * params.inventory_skew
        lower_reservation = fair - lower_position * params.inventory_skew

        if stale < params.stale_halt_steps:
            if ask <= fair - params.take_edge and position < limit:
                quantity = min(ask_volume, limit - position)
                if quantity > 0:
                    cash -= quantity * ask
                    position += quantity
            if bid >= fair + params.take_edge and position > -limit:
                quantity = min(bid_volume, position + limit)
                if quantity > 0:
                    cash += quantity * bid
                    position -= quantity

            if ask <= fair - params.take_edge and lower_position < limit:
                quantity = min(ask_volume, limit - lower_position)
                if quantity > 0:
                    lower_cash -= quantity * ask
                    lower_position += quantity
            if bid >= fair + params.take_edge and lower_position > -limit:
                quantity = min(bid_volume, lower_position + limit)
                if quantity > 0:
                    lower_cash += quantity * bid
                    lower_position -= quantity

        quote_edge = params.quote_edge + params.stale_widen * stale
        bid_quote = min(bid + 1, math.floor(reservation - quote_edge))
        ask_quote = max(ask - 1, math.ceil(reservation + quote_edge))

        if stale < params.stale_halt_steps or position < 0:
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

        if stale < params.stale_halt_steps or position > 0:
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

        last_valid_timestamp = timestamp
        last_book = (bid, bid_volume, ask, ask_volume)

    pnl = cash + position * day_book.last_valid_mid
    lower_pnl = lower_cash + lower_position * day_book.last_valid_mid
    return pnl, lower_pnl


def simulate_ipr_day(day_book: RawDayBook, params: IPRFreshParams) -> Tuple[float, float]:
    limit = POSITION_LIMITS["INTARIAN_PEPPER_ROOT"]
    cash = 0.0
    position = 0
    lower_cash = 0.0
    lower_position = 0
    last_valid_timestamp: int | None = None
    last_book: Tuple[int, int, int, int] | None = None
    day_open_mid: float | None = None
    day_open_timestamp: int | None = None

    for i in range(len(day_book.timestamp)):
        timestamp = int(day_book.timestamp[i])
        if not bool(day_book.valid[i]):
            continue

        bid = int(day_book.bid[i])
        ask = int(day_book.ask[i])
        bid_volume = int(day_book.bid_volume[i])
        ask_volume = int(day_book.ask_volume[i])
        micro_dev = float(day_book.micro_dev[i])
        trades = day_book.interval_trades[i]

        if day_open_mid is None or timestamp == 0:
            day_open_mid = (bid + ask) / 2.0
            day_open_timestamp = timestamp

        stale = stale_steps(timestamp, last_valid_timestamp)
        freshness = math.exp(-params.stale_decay * stale)
        ofi = normalized_ofi(bid, bid_volume, ask, ask_volume, last_book)
        signal = freshness * (params.microprice_weight * micro_dev + params.ofi_weight * ofi)
        trend_fair = day_open_mid + params.drift_per_timestamp * (timestamp - day_open_timestamp)
        fair = trend_fair + signal
        reservation = fair - position * params.inventory_skew
        lower_reservation = fair - lower_position * params.inventory_skew

        if stale < params.stale_halt_steps:
            if ask <= fair - params.take_edge and position < limit:
                quantity = min(ask_volume, limit - position)
                if quantity > 0:
                    cash -= quantity * ask
                    position += quantity
            if position > 0 and bid >= fair + params.take_edge:
                quantity = min(bid_volume, position + limit)
                if quantity > 0:
                    cash += quantity * bid
                    position -= quantity

            if ask <= fair - params.take_edge and lower_position < limit:
                quantity = min(ask_volume, limit - lower_position)
                if quantity > 0:
                    lower_cash -= quantity * ask
                    lower_position += quantity
            if lower_position > 0 and bid >= fair + params.take_edge:
                quantity = min(bid_volume, lower_position + limit)
                if quantity > 0:
                    lower_cash += quantity * bid
                    lower_position -= quantity

        bid_edge = params.bid_quote_edge + params.stale_widen * stale
        bid_quote = min(bid + 1, math.floor(reservation - bid_edge))
        if stale < params.stale_halt_steps:
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
            ask_edge = params.ask_quote_edge + params.stale_widen * stale
            ask_quote = max(ask - 1, math.ceil(reservation + ask_edge))
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

        last_valid_timestamp = timestamp
        last_book = (bid, bid_volume, ask, ask_volume)

    pnl = cash + position * day_book.last_valid_mid
    lower_pnl = lower_cash + lower_position * day_book.last_valid_mid
    return pnl, lower_pnl


def summarize_result(params, pnls: List[float], lower_pnls: List[float]) -> Dict:
    mean_pnl = float(np.mean(pnls))
    std_pnl = float(np.std(pnls))
    total_pnl = float(np.sum(pnls))
    total_lower = float(np.sum(lower_pnls))
    min_day = float(np.min(pnls))
    score = total_pnl + 0.35 * total_lower - 0.75 * std_pnl + 0.25 * min_day
    return {
        "params": params,
        "score": score,
        "total_pnl": total_pnl,
        "total_lower": total_lower,
        "day_pnls": tuple(round(pnl, 1) for pnl in pnls),
        "day_lower": tuple(round(pnl, 1) for pnl in lower_pnls),
    }


def evaluate_aco(books: Iterable[RawDayBook], params: ACOFreshParams) -> Dict:
    pnls = []
    lower_pnls = []
    for day_book in books:
        pnl, lower_pnl = simulate_aco_day(day_book, params)
        pnls.append(pnl)
        lower_pnls.append(lower_pnl)
    return summarize_result(params, pnls, lower_pnls)


def evaluate_ipr(books: Iterable[RawDayBook], params: IPRFreshParams) -> Dict:
    pnls = []
    lower_pnls = []
    for day_book in books:
        pnl, lower_pnl = simulate_ipr_day(day_book, params)
        pnls.append(pnl)
        lower_pnls.append(lower_pnl)
    return summarize_result(params, pnls, lower_pnls)


def sample_aco_candidates(count: int, seed: int) -> List[ACOFreshParams]:
    rng = random.Random(seed)
    candidates = set()
    while len(candidates) < count:
        candidates.add(
            ACOFreshParams(
                fair_value=10000.0,
                take_edge=rng.choice(ACO_GRID["take_edge"]),
                quote_edge=rng.choice(ACO_GRID["quote_edge"]),
                inventory_skew=rng.choice(ACO_GRID["inventory_skew"]),
                quote_size=rng.choice(ACO_GRID["quote_size"]),
                microprice_weight=rng.choice(ACO_GRID["microprice_weight"]),
                ofi_weight=rng.choice(ACO_GRID["ofi_weight"]),
                stale_decay=rng.choice(ACO_GRID["stale_decay"]),
                stale_widen=rng.choice(ACO_GRID["stale_widen"]),
                stale_halt_steps=rng.choice(ACO_GRID["stale_halt_steps"]),
            )
        )
    return list(candidates)


def sample_ipr_candidates(count: int, seed: int) -> List[IPRFreshParams]:
    rng = random.Random(seed)
    candidates = set()
    while len(candidates) < count:
        candidates.add(
            IPRFreshParams(
                drift_per_timestamp=rng.choice(IPR_GRID["drift_per_timestamp"]),
                take_edge=rng.choice(IPR_GRID["take_edge"]),
                bid_quote_edge=rng.choice(IPR_GRID["bid_quote_edge"]),
                ask_quote_edge=rng.choice(IPR_GRID["ask_quote_edge"]),
                inventory_skew=rng.choice(IPR_GRID["inventory_skew"]),
                quote_size=rng.choice(IPR_GRID["quote_size"]),
                microprice_weight=rng.choice(IPR_GRID["microprice_weight"]),
                ofi_weight=rng.choice(IPR_GRID["ofi_weight"]),
                stale_decay=rng.choice(IPR_GRID["stale_decay"]),
                stale_widen=rng.choice(IPR_GRID["stale_widen"]),
                stale_halt_steps=rng.choice(IPR_GRID["stale_halt_steps"]),
            )
        )
    return list(candidates)


def neighboring_candidates(params, grid: Dict[str, List]) -> List:
    variants = {params}
    for field_name, values in grid.items():
        current = getattr(params, field_name)
        index = values.index(current)
        neighbor_indexes = [index]
        if index > 0:
            neighbor_indexes.append(index - 1)
        if index + 1 < len(values):
            neighbor_indexes.append(index + 1)
        for neighbor_index in neighbor_indexes:
            variants.add(replace(params, **{field_name: values[neighbor_index]}))
    return list(variants)


def print_top_results(name: str, results: List[Dict], top_n: int = 5) -> None:
    print(f"\n{name} top {min(top_n, len(results))} candidates")
    for index, result in enumerate(results[:top_n], start=1):
        print(
            f"{index}. score={result['score']:.1f} total_pnl={result['total_pnl']:.1f} "
            f"lower={result['total_lower']:.1f} day_pnls={result['day_pnls']} params={result['params']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the freshness-skew Round 1 strategy.")
    parser.add_argument("--aco-samples", type=int, default=180)
    parser.add_argument("--ipr-samples", type=int, default=260)
    parser.add_argument("--topk", type=int, default=8)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    prices = load_prices()
    trades = load_trades()
    books = build_day_books(prices, trades)

    coarse_aco = sample_aco_candidates(args.aco_samples, args.seed)
    coarse_aco_results = [evaluate_aco(books["ASH_COATED_OSMIUM"], params) for params in coarse_aco]
    coarse_aco_results.sort(key=lambda result: result["score"], reverse=True)
    print_top_results("ACO coarse", coarse_aco_results)

    refine_aco = set()
    for result in coarse_aco_results[: args.topk]:
        refine_aco.update(neighboring_candidates(result["params"], ACO_GRID))
    refined_aco_results = [evaluate_aco(books["ASH_COATED_OSMIUM"], params) for params in refine_aco]
    refined_aco_results.sort(key=lambda result: result["score"], reverse=True)
    print_top_results("ACO refined", refined_aco_results)

    coarse_ipr = sample_ipr_candidates(args.ipr_samples, args.seed + 1)
    coarse_ipr_results = [evaluate_ipr(books["INTARIAN_PEPPER_ROOT"], params) for params in coarse_ipr]
    coarse_ipr_results.sort(key=lambda result: result["score"], reverse=True)
    print_top_results("IPR coarse", coarse_ipr_results)

    refine_ipr = set()
    for result in coarse_ipr_results[: args.topk]:
        refine_ipr.update(neighboring_candidates(result["params"], IPR_GRID))
    refined_ipr_results = [evaluate_ipr(books["INTARIAN_PEPPER_ROOT"], params) for params in refine_ipr]
    refined_ipr_results.sort(key=lambda result: result["score"], reverse=True)
    print_top_results("IPR refined", refined_ipr_results)

    print("\nBest parameters to copy into freshness_skew.py")
    print("ACO", refined_aco_results[0]["params"])
    print("IPR", refined_ipr_results[0]["params"])


if __name__ == "__main__":
    main()
