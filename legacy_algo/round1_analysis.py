from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("ROUND1")
PRICE_FILES = sorted(ROOT.glob("prices_round_1_day_*.csv"))
TRADE_FILES = sorted(ROOT.glob("trades_round_1_day_*.csv"))
POSITION_LIMITS = {
    "ASH_COATED_OSMIUM": 50,
    "INTARIAN_PEPPER_ROOT": 50,
}


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
    prices["clean_mid"] = np.where(
        prices["has_top_book"],
        (prices["bid_price_1"] + prices["ask_price_1"]) / 2.0,
        np.nan,
    )
    prices["spread"] = prices["ask_price_1"] - prices["bid_price_1"]
    prices["imbalance"] = (
        prices["bid_volume_1"].fillna(0) - prices["ask_volume_1"].fillna(0)
    ) / (
        prices["bid_volume_1"].fillna(0) + prices["ask_volume_1"].fillna(0)
    ).replace(0, np.nan)
    prices["microprice"] = (
        prices["ask_price_1"] * prices["bid_volume_1"].fillna(0)
        + prices["bid_price_1"] * prices["ask_volume_1"].fillna(0)
    ) / (
        prices["bid_volume_1"].fillna(0) + prices["ask_volume_1"].fillna(0)
    ).replace(0, np.nan)
    prices["micro_dev"] = prices["microprice"] - prices["clean_mid"]
    return prices.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)


def load_trades() -> pd.DataFrame:
    trades = []
    for path in TRADE_FILES:
        frame = pd.read_csv(path, sep=";")
        frame["day"] = int(path.stem.split("_")[-1])
        trades.append(frame)
    all_trades = pd.concat(trades, ignore_index=True)
    all_trades["timestamp"] = pd.to_numeric(all_trades["timestamp"], errors="coerce")
    return all_trades


def simulate_top_of_book(df: pd.DataFrame, fair_values: np.ndarray, threshold: float, limit: int) -> tuple[float, int]:
    bid = df["bid_price_1"].to_numpy()
    ask = df["ask_price_1"].to_numpy()
    bid_volume = np.nan_to_num(df["bid_volume_1"].to_numpy(), nan=0).astype(int)
    ask_volume = np.nan_to_num(df["ask_volume_1"].to_numpy(), nan=0).astype(int)
    last_mid = float(df["clean_mid"].iloc[-1])

    pnl = 0.0
    position = 0
    trades = 0

    for index in range(len(df)):
        if ask[index] <= fair_values[index] - threshold and position < limit:
            quantity = min(ask_volume[index], limit - position)
            if quantity > 0:
                pnl -= quantity * ask[index]
                position += quantity
                trades += 1

        if bid[index] >= fair_values[index] + threshold and position > -limit:
            quantity = min(bid_volume[index], position + limit)
            if quantity > 0:
                pnl += quantity * bid[index]
                position -= quantity
                trades += 1

    pnl += position * last_mid
    return pnl, trades


def summarize_prices(prices: pd.DataFrame) -> None:
    clean = prices[prices["has_top_book"]].copy()

    print("Round 1 data quality")
    invalid_counts = prices.groupby("product").apply(lambda frame: (~frame["has_top_book"]).sum())
    for product_name, invalid_count in invalid_counts.items():
        print(f"- {product_name}: {invalid_count} invalid top-of-book rows out of {len(prices[prices['product'] == product_name])}")
    print()

    for product_name, frame in clean.groupby("product"):
        print(product_name)
        by_day = frame.groupby("day")["clean_mid"].agg(["first", "last", "mean", "std", "min", "max"])
        print(by_day.round(3).to_string())

        frame["fwd_ret_1"] = frame.groupby("day")["clean_mid"].shift(-1) - frame["clean_mid"]
        print("spread mean/std:", round(frame["spread"].mean(), 3), round(frame["spread"].std(), 3))
        print(
            "corr(imbalance, next mid change):",
            round(frame[["imbalance", "fwd_ret_1"]].dropna().corr().iloc[0, 1], 4),
        )
        print(
            "corr(micro_dev, next mid change):",
            round(frame[["micro_dev", "fwd_ret_1"]].dropna().corr().iloc[0, 1], 4),
        )

        if product_name == "INTARIAN_PEPPER_ROOT":
            for day, day_frame in frame.groupby("day"):
                slope = np.polyfit(day_frame["timestamp"].to_numpy(), day_frame["clean_mid"].to_numpy(), 1)[0]
                print(f"day {day} linear slope per timestamp: {slope:.6f}")

        print()


def summarize_trades(trades: pd.DataFrame) -> None:
    print("Executed trade summary")
    summary = trades.groupby("symbol").agg(
        trade_count=("quantity", "size"),
        total_quantity=("quantity", "sum"),
        average_quantity=("quantity", "mean"),
        average_price=("price", "mean"),
        price_std=("price", "std"),
    )
    print(summary.round(3).to_string())
    print()


def run_baseline_backtests(prices: pd.DataFrame) -> None:
    clean = prices[prices["has_top_book"]].copy()
    clean["micro_dev"] = clean["micro_dev"].fillna(0.0)

    print("Simple top-of-book baseline backtests")

    aco = clean[clean["product"] == "ASH_COATED_OSMIUM"].reset_index(drop=True)
    aco_results = []
    for micro_weight, threshold in product([0.0, 0.5, 1.0, 1.5, 2.0], [0.0, 0.5, 1.0, 2.0, 3.0, 4.0]):
        fair_values = 10000.0 + micro_weight * aco["micro_dev"].to_numpy()
        pnl, trades = simulate_top_of_book(
            aco,
            fair_values,
            threshold,
            POSITION_LIMITS["ASH_COATED_OSMIUM"],
        )
        aco_results.append((pnl, trades, micro_weight, threshold))
    best_aco = max(aco_results, key=lambda row: row[0])
    print(
        "ASH_COATED_OSMIUM best rule:",
        f"fixed fair 10000 + {best_aco[2]} * micro_dev, threshold {best_aco[3]}, pnl {best_aco[0]:.1f}, trades {best_aco[1]}",
    )

    ipr = clean[clean["product"] == "INTARIAN_PEPPER_ROOT"].reset_index(drop=True)
    day_open = ipr.groupby("day")["clean_mid"].first()
    day_open_ts = ipr.groupby("day")["timestamp"].first()
    timestamp_offset = ipr["timestamp"].to_numpy() - ipr["day"].map(day_open_ts).to_numpy()
    ipr_results = []
    for slope, micro_weight, threshold in product(
        [0.0008, 0.0009, 0.0010, 0.0011, 0.0012],
        [0.0, 0.5, 1.0, 1.5, 2.0],
        [0.0, 0.5, 1.0, 2.0, 3.0],
    ):
        fair_values = (
            ipr["day"].map(day_open).to_numpy()
            + slope * timestamp_offset
            + micro_weight * ipr["micro_dev"].to_numpy()
        )
        pnl, trades = simulate_top_of_book(
            ipr,
            fair_values,
            threshold,
            POSITION_LIMITS["INTARIAN_PEPPER_ROOT"],
        )
        ipr_results.append((pnl, trades, slope, micro_weight, threshold))
    best_ipr = max(ipr_results, key=lambda row: row[0])
    print(
        "INTARIAN_PEPPER_ROOT best rule:",
        f"open anchored trend slope {best_ipr[2]:.4f} + {best_ipr[3]} * micro_dev, threshold {best_ipr[4]}, pnl {best_ipr[0]:.1f}, trades {best_ipr[1]}",
    )
    print()


def main() -> None:
    prices = load_prices()
    trades = load_trades()
    summarize_prices(prices)
    summarize_trades(trades)
    run_baseline_backtests(prices)


if __name__ == "__main__":
    main()
