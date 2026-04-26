"""Grid search osmium params with spread-regime adaptation.

Extends ACOParams with:
  tight_threshold / wide_threshold  — spread bucket boundaries
  tight_inside_offset / normal_inside_offset / wide_inside_offset  — ticks above best_bid (below best_ask) to quote
  skip_quote_in_tight  — if True, no passive quotes when spread is tight (take-only)
  tight_quote_size / wide_quote_size — regime-specific sizing (same scale as QUOTE_SIZE)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Iterable, List, Tuple

import numpy as np

from legacy_algo.train_round1_strategy import (
    DayBook,
    POSITION_LIMITS,
    build_day_books,
    load_prices,
    load_trades,
    passive_buy_fill,
    passive_sell_fill,
    summarize_result,
)


@dataclass(frozen=True)
class AdaptiveACOParams:
    fair_value: float
    take_edge: float
    quote_edge: float
    inventory_skew: float
    normal_quote_size: int
    tight_threshold: int
    wide_threshold: int
    normal_inside_offset: int
    tight_inside_offset: int
    wide_inside_offset: int
    skip_quote_in_tight: bool
    tight_quote_size: int
    wide_quote_size: int


def simulate(day_book: DayBook, p: AdaptiveACOParams) -> Tuple[float, float]:
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

        spread = ask - bid
        if spread <= p.tight_threshold:
            inside_offset = p.tight_inside_offset
            quote_size_regime = p.tight_quote_size
            skip_passive = p.skip_quote_in_tight
        elif spread >= p.wide_threshold:
            inside_offset = p.wide_inside_offset
            quote_size_regime = p.wide_quote_size
            skip_passive = False
        else:
            inside_offset = p.normal_inside_offset
            quote_size_regime = p.normal_quote_size
            skip_passive = False

        reservation = p.fair_value - position * p.inventory_skew
        lower_reservation = p.fair_value - lower_position * p.inventory_skew

        # --- Aggressive takes (same for both passive and lower-bound books) ---
        if ask <= reservation - p.take_edge and position < limit:
            qty = min(ask_volume, limit - position)
            if qty > 0:
                cash -= qty * ask
                position += qty

        if bid >= reservation + p.take_edge and position > -limit:
            qty = min(bid_volume, position + limit)
            if qty > 0:
                cash += qty * bid
                position -= qty

        if ask <= lower_reservation - p.take_edge and lower_position < limit:
            qty = min(ask_volume, limit - lower_position)
            if qty > 0:
                lower_cash -= qty * ask
                lower_position += qty

        if bid >= lower_reservation + p.take_edge and lower_position > -limit:
            qty = min(bid_volume, lower_position + limit)
            if qty > 0:
                lower_cash += qty * bid
                lower_position -= qty

        # --- Passive quotes (only in non-lower book) ---
        if skip_passive:
            continue

        bid_quote = min(bid + inside_offset, math.floor(reservation - p.quote_edge))
        ask_quote = max(ask - inside_offset, math.ceil(reservation + p.quote_edge))

        bid_size = min(quote_size_regime, limit - position)
        if bid_size > 0 and bid_quote > 0 and bid_quote < ask:
            filled = passive_buy_fill(bid_quote, bid_size, bid, int(day_book.next_ask[i]), trades)
            if filled > 0:
                cash -= filled * bid_quote
                position += filled

        ask_size = min(quote_size_regime, limit + position)
        if ask_size > 0 and ask_quote > bid:
            filled = passive_sell_fill(ask_quote, ask_size, ask, int(day_book.next_bid[i]), trades)
            if filled > 0:
                cash += filled * ask_quote
                position -= filled

    pnl = cash + position * day_book.last_mid
    lower_pnl = lower_cash + lower_position * day_book.last_mid
    return pnl, lower_pnl


def evaluate(books: List[DayBook], params: AdaptiveACOParams) -> dict:
    pnls = []
    lower_pnls = []
    for book in books:
        pnl, lower_pnl = simulate(book, params)
        pnls.append(pnl)
        lower_pnls.append(lower_pnl)
    return summarize_result(params, pnls, lower_pnls)


def candidates() -> Iterable[AdaptiveACOParams]:
    # Fix baseline to prior best; only vary the adaptive dimensions.
    fair = 10001.0
    take = 0.5
    qedge = 1.25
    skew = 0.12
    n_size = 16
    tt = 11
    wt = 18
    n_off = 1

    tight_offsets = [1, 2, 3, 4]
    wide_offsets = [1, 2, 3, 4, 5, 6, 7]
    skip_in_tight = [False, True]
    tight_sizes = [8, 12, 16]
    wide_sizes = [16, 20]

    for (t_off, w_off, skip_t, t_sz, w_sz) in product(
        tight_offsets, wide_offsets, skip_in_tight, tight_sizes, wide_sizes
    ):
        yield AdaptiveACOParams(
            fair_value=fair,
            take_edge=take,
            quote_edge=qedge,
            inventory_skew=skew,
            normal_quote_size=n_size,
            tight_threshold=tt,
            wide_threshold=wt,
            normal_inside_offset=n_off,
            tight_inside_offset=t_off,
            wide_inside_offset=w_off,
            skip_quote_in_tight=skip_t,
            tight_quote_size=t_sz,
            wide_quote_size=w_sz,
        )


def main() -> None:
    prices = load_prices()
    trades = load_trades()
    books = build_day_books(prices, trades)
    osmium = books["ASH_COATED_OSMIUM"]

    all_candidates = list(candidates())
    print(f"Evaluating {len(all_candidates)} candidates...")

    results = [evaluate(osmium, params) for params in all_candidates]
    results.sort(key=lambda r: r["score"], reverse=True)

    print(f"\nTop 15 spread-adaptive candidates:")
    for i, r in enumerate(results[:15], 1):
        p = r["params"]
        print(
            f"{i}. score={r['score']:.1f} pnl={r['total_pnl']:.1f} lower={r['total_lower']:.1f}\n"
            f"    days={r['day_pnls']}\n"
            f"    fair={p.fair_value} take={p.take_edge} qedge={p.quote_edge} skew={p.inventory_skew} nsize={p.normal_quote_size}\n"
            f"    tight(<={p.tight_threshold}): skip={p.skip_quote_in_tight} offset={p.tight_inside_offset} size={p.tight_quote_size}\n"
            f"    wide(>={p.wide_threshold}): offset={p.wide_inside_offset} size={p.wide_quote_size}"
        )

    print(f"\nBaseline (non-adaptive, prior best): PnL ~46842")
    best = results[0]
    print(f"Best adaptive PnL: {best['total_pnl']:.1f}  (delta vs baseline: {best['total_pnl'] - 46842:+.1f})")


if __name__ == "__main__":
    main()
