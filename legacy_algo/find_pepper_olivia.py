from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1] / "ROUND_2"
DAYS = (-1, 0, 1)
PRODUCT = "INTARIAN_PEPPER_ROOT"


def load_round2() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = pd.concat(
        [pd.read_csv(ROOT / f"prices_round_2_day_{day}.csv", sep=";").assign(day=day) for day in DAYS],
        ignore_index=True,
    )
    trades = pd.concat(
        [pd.read_csv(ROOT / f"trades_round_2_day_{day}.csv", sep=";").assign(day=day) for day in DAYS],
        ignore_index=True,
    )
    return prices, trades


def fit_pepper_fair(prices: pd.DataFrame) -> np.ndarray:
    pepper = prices[(prices["product"] == PRODUCT) & (prices["mid_price"] > 0)].copy()
    x = np.c_[
        np.ones(len(pepper)),
        pepper["day"].to_numpy(),
        pepper["timestamp"].to_numpy(),
    ]
    y = pepper["mid_price"].to_numpy()
    return np.linalg.lstsq(x, y, rcond=None)[0]


def enrich_trades(prices: pd.DataFrame, trades: pd.DataFrame, beta: np.ndarray) -> pd.DataFrame:
    pepper_prices = prices[prices["product"] == PRODUCT].sort_values(["day", "timestamp"]).copy()
    pepper_prices["mid_fwd_10"] = pepper_prices.groupby("day")["mid_price"].shift(-10)
    lookup = pepper_prices.set_index(["day", "timestamp"])

    pepper_trades = trades[trades["symbol"] == PRODUCT].copy()
    rows: list[dict[str, float | int | str]] = []

    for trade in pepper_trades.itertuples(index=False):
        key = (int(trade.day), int(trade.timestamp))
        if key not in lookup.index:
            continue

        snapshot = lookup.loc[key]
        mid = float(snapshot["mid_price"])
        if mid <= 0:
            continue

        fair = float(beta[0] + beta[1] * trade.day + beta[2] * trade.timestamp)
        price = float(trade.price)
        quantity = int(trade.quantity)
        side = "BUY" if price > mid else "SELL" if price < mid else "MID"
        edge = fair - price if side == "BUY" else price - fair if side == "SELL" else abs(fair - price)

        markout_10 = np.nan
        mid_fwd_10 = float(snapshot["mid_fwd_10"]) if not pd.isna(snapshot["mid_fwd_10"]) else np.nan
        if not np.isnan(mid_fwd_10) and mid_fwd_10 > 0:
            markout_10 = mid_fwd_10 - mid if side == "BUY" else mid - mid_fwd_10 if side == "SELL" else abs(mid_fwd_10 - mid)

        rows.append(
            {
                "day": int(trade.day),
                "timestamp": int(trade.timestamp),
                "price": price,
                "mid": mid,
                "fair": fair,
                "quantity": quantity,
                "side": side,
                "signed_edge": edge,
                "residual": mid - fair,
                "markout_10": markout_10,
            }
        )

    return pd.DataFrame(rows)


def print_summary(enriched: pd.DataFrame, quantity: int, min_repeat: int) -> None:
    bucket = enriched[(enriched["quantity"] == quantity) & (enriched["side"] != "MID")].copy()

    print("Pepper Olivia detector")
    print(f"dataset: {ROOT}")
    print(f"candidate size: {quantity}")
    print()

    if bucket.empty:
        print("No candidate trades found.")
        return

    print("Candidate bucket summary")
    print(
        bucket.groupby("side")[["signed_edge", "markout_10"]]
        .agg(["count", "mean", "median"])
        .round(3)
        .to_string()
    )
    print()

    repeats = (
        bucket.groupby("timestamp")
        .agg(
            count=("day", "size"),
            days=("day", lambda s: list(sorted(int(x) for x in s))),
            sides=("side", lambda s: list(s)),
        )
        .reset_index()
    )
    repeats = repeats[repeats["count"] >= min_repeat].sort_values(["count", "timestamp"], ascending=[False, True])

    print(f"Recurring timestamps with at least {min_repeat} repeats")
    if repeats.empty:
        print("None")
    else:
        print(repeats.to_string(index=False))
    print()

    consistent = repeats[repeats["sides"].map(lambda values: len(set(values)) == 1)].copy()
    buy_times = sorted(int(ts) for ts in consistent[consistent["sides"].map(lambda values: values[0] == "BUY")]["timestamp"])
    sell_times = sorted(int(ts) for ts in consistent[consistent["sides"].map(lambda values: values[0] == "SELL")]["timestamp"])

    print("Consistent schedule candidates")
    print(f"BUY_TIMESTAMPS = {buy_times}")
    print(f"SELL_TIMESTAMPS = {sell_times}")
    print()

    print("Strongest candidate prints")
    top = bucket.sort_values(["signed_edge", "markout_10"], ascending=[False, False]).head(20)
    print(top[["day", "timestamp", "side", "price", "mid", "fair", "signed_edge", "markout_10"]].round(3).to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Find Olivia-like Pepper prints in ROUND_2.")
    parser.add_argument("--quantity", type=int, default=8, help="Trade size to inspect")
    parser.add_argument("--min-repeat", type=int, default=2, help="Minimum repeat count for schedule output")
    args = parser.parse_args()

    prices, trades = load_round2()
    beta = fit_pepper_fair(prices)

    print(
        "fitted fair(day, timestamp) ~= "
        f"{beta[0]:.6f} + {beta[1]:.6f} * day + {beta[2]:.9f} * timestamp"
    )
    print()

    enriched = enrich_trades(prices, trades, beta)
    print_summary(enriched, quantity=args.quantity, min_repeat=args.min_repeat)


if __name__ == "__main__":
    main()
