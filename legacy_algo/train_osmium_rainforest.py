"""Focused grid search for ASH_COATED_OSMIUM params.

Reuses the simulation primitives from train_round1_strategy so the passive-fill
queue model, lower-bound replay, and scoring stay consistent.
"""
from __future__ import annotations

from itertools import product
from typing import Iterable, List

import numpy as np

from train_round1_strategy import (
    ACOParams,
    evaluate_aco,
    build_day_books,
    load_prices,
    load_trades,
)


def expanded_aco_grid() -> Iterable[ACOParams]:
    fair_values = [9999.5, 10000.0, 10000.5]
    take_edges = [0.5, 1.0, 1.5, 2.0]
    quote_edges = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    inventory_skews = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25]
    quote_sizes = [10, 12, 14, 16, 20]

    for fair, take, quote, skew, size in product(
        fair_values, take_edges, quote_edges, inventory_skews, quote_sizes
    ):
        yield ACOParams(
            fair_value=fair,
            take_edge=take,
            quote_edge=quote,
            inventory_skew=skew,
            quote_size=size,
        )


def refine(base: ACOParams) -> List[ACOParams]:
    variants = set()
    for df in (-0.5, -0.25, 0.0, 0.25, 0.5):
        for dt in (-0.25, 0.0, 0.25):
            for dq in (-0.25, 0.0, 0.25):
                for ds in (-0.02, 0.0, 0.02):
                    for dsz in (-2, 0, 2):
                        candidate = ACOParams(
                            fair_value=round(base.fair_value + df, 3),
                            take_edge=max(0.25, round(base.take_edge + dt, 3)),
                            quote_edge=max(0.5, round(base.quote_edge + dq, 3)),
                            inventory_skew=max(0.01, round(base.inventory_skew + ds, 4)),
                            quote_size=max(4, base.quote_size + dsz),
                        )
                        variants.add(candidate)
    return list(variants)


def main() -> None:
    prices = load_prices()
    trades = load_trades()
    books = build_day_books(prices, trades)
    osmium = books["ASH_COATED_OSMIUM"]

    print("Stage 1: expanded grid")
    results = [evaluate_aco(osmium, params) for params in expanded_aco_grid()]
    results.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(results[:10], 1):
        print(
            f"{i}. score={r['score']:.1f} pnl={r['total_pnl']:.1f} lower={r['total_lower']:.1f} "
            f"days={r['day_pnls']} {r['params']}"
        )

    best = results[0]["params"]
    print(f"\nStage 2: refine around {best}")
    refined = [evaluate_aco(osmium, params) for params in refine(best)]
    refined.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(refined[:10], 1):
        print(
            f"{i}. score={r['score']:.1f} pnl={r['total_pnl']:.1f} lower={r['total_lower']:.1f} "
            f"days={r['day_pnls']} {r['params']}"
        )

    print(f"\nBEST OSMIUM PARAMS:")
    print(refined[0]["params"])
    print(f"  per-day PnL: {refined[0]['day_pnls']}")
    print(f"  total PnL: {refined[0]['total_pnl']:.1f}")
    print(f"  aggressive-only lower bound: {refined[0]['total_lower']:.1f}")


if __name__ == "__main__":
    main()
