from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


ROOT = Path(__file__).resolve().parent


def _split_lines(text: str) -> list[str]:
    text = dedent(text).strip("\n")
    if not text:
        return []
    return [line + "\n" for line in text.splitlines()]


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": _split_lines(text),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _split_lines(text),
    }


COMMON_HELPERS = """
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["figure.figsize"] = (12, 4)
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 200)

ROUND1_DIR = Path("ROUND1")
ROUND2_DIR = Path("ROUND_2")
PRODUCTS = ["ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"]
SHORT = {"ASH_COATED_OSMIUM": "ACO", "INTARIAN_PEPPER_ROOT": "IPR"}
COLORS = {"ACO": "#1f77b4", "IPR": "#d62728"}


def load_round(folder: Path, round_num: int):
    prices = []
    for path in sorted(folder.glob(f"prices_round_{round_num}_day_*.csv")):
        df = pd.read_csv(path, sep=";")
        prices.append(df)
    prices = pd.concat(prices, ignore_index=True)
    prices["t"] = prices["day"] * 1_000_000 + prices["timestamp"]

    trades = []
    for path in sorted(folder.glob(f"trades_round_{round_num}_day_*.csv")):
        df = pd.read_csv(path, sep=";")
        df["day"] = int(path.stem.split("day_")[-1])
        df["t"] = df["day"] * 1_000_000 + df["timestamp"]
        trades.append(df)
    trades = pd.concat(trades, ignore_index=True)
    return prices, trades


def prepare_features(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["depth_top"] = df["bid_volume_1"].fillna(0) + df["ask_volume_1"].fillna(0)
    df["depth_l2"] = df["bid_volume_2"].fillna(0) + df["ask_volume_2"].fillna(0)
    df["depth_l3"] = df["bid_volume_3"].fillna(0) + df["ask_volume_3"].fillna(0)
    denom = (df["bid_volume_1"].fillna(0) + df["ask_volume_1"].fillna(0)).replace(0, np.nan)
    df["imbalance"] = (df["bid_volume_1"].fillna(0) - df["ask_volume_1"].fillna(0)) / denom
    df["microprice"] = (
        df["ask_price_1"] * df["bid_volume_1"] + df["bid_price_1"] * df["ask_volume_1"]
    ) / (df["bid_volume_1"] + df["ask_volume_1"])
    df["micro_delta"] = df["microprice"] - df["mid_price"]
    return df


def clean_mid(df: pd.DataFrame, product: str | None = None) -> pd.DataFrame:
    out = df[df["mid_price"] > 0].copy()
    if product is not None:
        out = out[out["product"] == product].copy()
    return out.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)


def aco_regime_metrics(df: pd.DataFrame) -> pd.Series:
    sub = clean_mid(df, "ASH_COATED_OSMIUM")
    lag = sub["mid_price"].shift(1)
    cur = sub["mid_price"]
    reg = pd.DataFrame({"lag": lag, "cur": cur}).dropna()
    phi, intercept = np.polyfit(reg["lag"], reg["cur"], 1)
    halflife = -np.log(2) / np.log(phi)
    fair = intercept / (1 - phi)
    rets = np.log(sub["mid_price"]).diff().dropna()
    return pd.Series(
        {
            "fair_value": fair,
            "mid_std": sub["mid_price"].std(),
            "spread_mean": sub["spread"].mean(),
            "ou_phi": phi,
            "ou_half_life_ticks": halflife,
            "ret_autocorr_1": rets.autocorr(1),
        }
    )


def ipr_trend_fit(df: pd.DataFrame):
    sub = clean_mid(df, "INTARIAN_PEPPER_ROOT")
    X = np.column_stack(
        [np.ones(len(sub)), sub["day"].to_numpy(), sub["timestamp"].to_numpy()]
    )
    beta, *_ = np.linalg.lstsq(X, sub["mid_price"].to_numpy(), rcond=None)
    sub["fair_formula"] = X @ beta
    sub["trend_resid"] = sub["mid_price"] - sub["fair_formula"]
    return sub, beta


def ipr_regime_metrics(df: pd.DataFrame) -> pd.Series:
    sub, beta = ipr_trend_fit(df)
    resid = sub["trend_resid"]
    lag = resid.shift(1)
    cur = resid
    reg = pd.DataFrame({"lag": lag, "cur": cur}).dropna()
    phi, intercept = np.polyfit(reg["lag"], reg["cur"], 1)
    halflife = -np.log(2) / np.log(phi) if 0 < phi < 1 else np.nan
    rets = np.log(sub["mid_price"]).diff().dropna()
    return pd.Series(
        {
            "formula_intercept": beta[0],
            "formula_day_coef": beta[1],
            "formula_timestamp_coef": beta[2],
            "resid_std": resid.std(),
            "resid_min": resid.min(),
            "resid_max": resid.max(),
            "resid_phi": phi,
            "resid_half_life_ticks": halflife,
            "ret_autocorr_1": rets.autocorr(1),
            "spread_mean": sub["spread"].mean(),
        }
    )


def quality_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product in PRODUCTS:
        sub = df[df["product"] == product].copy()
        rows.append(
            {
                "product": product,
                "rows": len(sub),
                "days": sub["day"].nunique(),
                "mid_zero_rows": int((sub["mid_price"] == 0).sum()),
                "mid_mean_clean": sub.loc[sub["mid_price"] > 0, "mid_price"].mean(),
                "mid_std_clean": sub.loc[sub["mid_price"] > 0, "mid_price"].std(),
                "spread_mean": sub.loc[sub["mid_price"] > 0, "spread"].mean(),
                "top_depth_mean": sub.loc[sub["mid_price"] > 0, "depth_top"].mean(),
                "l3_bid_presence": sub["bid_price_3"].notna().mean(),
                "l3_ask_presence": sub["ask_price_3"].notna().mean(),
            }
        )
    out = pd.DataFrame(rows).set_index("product")
    return out.round(4)


def regime_table(df: pd.DataFrame) -> pd.DataFrame:
    aco = aco_regime_metrics(df).rename("ASH_COATED_OSMIUM")
    ipr = ipr_regime_metrics(df).rename("INTARIAN_PEPPER_ROOT")
    out = pd.concat([aco, ipr], axis=1)
    return out.round(6)


def compare_rounds(round1_prices: pd.DataFrame, round2_prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, df in [("round1", round1_prices), ("round2", round2_prices)]:
        aco = aco_regime_metrics(df)
        ipr = ipr_regime_metrics(df)
        rows.extend(
            [
                {
                    "round": label,
                    "product": "ASH_COATED_OSMIUM",
                    "fair_value": aco["fair_value"],
                    "mid_std": aco["mid_std"],
                    "spread_mean": aco["spread_mean"],
                    "half_life_ticks": aco["ou_half_life_ticks"],
                },
                {
                    "round": label,
                    "product": "INTARIAN_PEPPER_ROOT",
                    "timestamp_slope": ipr["formula_timestamp_coef"],
                    "day_slope": ipr["formula_day_coef"],
                    "resid_std": ipr["resid_std"],
                    "spread_mean": ipr["spread_mean"],
                },
            ]
        )
    out = pd.DataFrame(rows).set_index(["product", "round"])
    return out.round(6)


def horizon_signal_table(df: pd.DataFrame, product: str, horizons=(1, 2, 5, 10, 20, 50)) -> pd.DataFrame:
    sub = clean_mid(df, product)
    if product == "ASH_COATED_OSMIUM":
        sub["rolling_mean"] = sub["mid_price"].rolling(200, min_periods=50).mean()
        sub["rolling_std"] = sub["mid_price"].rolling(200, min_periods=50).std()
        sub["price_z"] = (sub["mid_price"] - sub["rolling_mean"]) / sub["rolling_std"]
        signals = {
            "imbalance": sub["imbalance"],
            "micro_delta": sub["micro_delta"],
            "price_z": sub["price_z"],
        }
    else:
        sub, _ = ipr_trend_fit(df)
        resid_std = sub["trend_resid"].std()
        sub["trend_z"] = sub["trend_resid"] / resid_std
        signals = {
            "imbalance": sub["imbalance"],
            "micro_delta": sub["micro_delta"],
            "trend_z": sub["trend_z"],
        }
    rows = []
    for horizon in horizons:
        fut = sub["mid_price"].shift(-horizon) - sub["mid_price"]
        mask = fut.notna()
        row = {"horizon_ticks": horizon}
        for name, signal in signals.items():
            row[name] = signal[mask].corr(fut[mask])
        rows.append(row)
    return pd.DataFrame(rows).set_index("horizon_ticks").round(4)


def markout_table(df: pd.DataFrame, product: str, signal_name: str, horizon: int = 10) -> pd.DataFrame:
    sub = clean_mid(df, product)
    if signal_name == "imbalance":
        signal = sub["imbalance"]
    elif signal_name == "micro_delta":
        signal = sub["micro_delta"]
    elif signal_name == "price_z":
        rolling_mean = sub["mid_price"].rolling(200, min_periods=50).mean()
        rolling_std = sub["mid_price"].rolling(200, min_periods=50).std()
        signal = (sub["mid_price"] - rolling_mean) / rolling_std
    elif signal_name == "trend_z":
        sub, _ = ipr_trend_fit(df)
        signal = sub["trend_resid"] / sub["trend_resid"].std()
    else:
        raise ValueError(f"Unsupported signal: {signal_name}")

    frame = pd.DataFrame({"signal": signal, "mid_price": sub["mid_price"]}).dropna()
    frame["future_move"] = frame["mid_price"].shift(-horizon) - frame["mid_price"]
    frame = frame.dropna()
    raw_buckets = pd.qcut(frame["signal"], 5, duplicates="drop")
    categories = raw_buckets.cat.categories
    labels = [f"Q{i}" for i in range(1, len(categories) + 1)]
    frame["bucket"] = pd.Categorical.from_codes(raw_buckets.cat.codes, labels)
    out = (
        frame.groupby("bucket", observed=False)
        .agg(obs=("future_move", "size"), avg_future_move=("future_move", "mean"), avg_signal=("signal", "mean"))
        .round(4)
    )
    return out


def threshold_markouts(df: pd.DataFrame, product: str, horizon: int = 10) -> pd.DataFrame:
    sub = clean_mid(df, product)
    if product == "ASH_COATED_OSMIUM":
        rolling_mean = sub["mid_price"].rolling(200, min_periods=50).mean()
        rolling_std = sub["mid_price"].rolling(200, min_periods=50).std()
        sub["z"] = (sub["mid_price"] - rolling_mean) / rolling_std
        sub["future_move"] = sub["mid_price"].shift(-horizon) - sub["mid_price"]
        rows = []
        for k in [0.5, 1.0, 1.5]:
            buy = sub.loc[sub["z"] <= -k, "future_move"].dropna()
            sell = sub.loc[sub["z"] >= k, "future_move"].dropna()
            rows.append({"threshold": k, "buy_obs": len(buy), "buy_avg_markout": buy.mean(), "sell_obs": len(sell), "sell_avg_markout": sell.mean()})
        return pd.DataFrame(rows).set_index("threshold").round(4)

    sub, beta = ipr_trend_fit(df)
    sigma = sub["trend_resid"].std()
    sub["future_move"] = sub["mid_price"].shift(-horizon) - sub["mid_price"]
    rows = []
    for k in [0.5, 1.0, 1.5, 2.0]:
        buy = sub.loc[sub["trend_resid"] <= -k * sigma, "future_move"].dropna()
        sell = sub.loc[sub["trend_resid"] >= k * sigma, "future_move"].dropna()
        rows.append({"threshold_sigma": k, "buy_obs": len(buy), "buy_avg_markout": buy.mean(), "sell_obs": len(sell), "sell_avg_markout": sell.mean()})
    return pd.DataFrame(rows).set_index("threshold_sigma").round(4)


def align_trades_to_book(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for product in PRODUCTS:
        for day in sorted(prices["day"].unique()):
            book = clean_mid(prices, product)
            book = book[book["day"] == day][["timestamp", "day", "bid_price_1", "ask_price_1", "mid_price"]].sort_values("timestamp")
            tape = trades[(trades["symbol"] == product) & (trades["day"] == day)].sort_values("timestamp").copy()
            if tape.empty or book.empty:
                continue
            merged = pd.merge_asof(tape, book, on="timestamp", by="day", direction="backward")
            parts.append(merged)
    aligned = pd.concat(parts, ignore_index=True)
    aligned["rel_mid"] = aligned["price"] - aligned["mid_price"]
    aligned["side"] = np.where(
        np.isclose(aligned["price"], aligned["ask_price_1"]),
        "buy",
        np.where(np.isclose(aligned["price"], aligned["bid_price_1"]), "sell", "inside"),
    )
    return aligned


def trade_summary(aligned: pd.DataFrame) -> pd.DataFrame:
    out = (
        aligned.groupby("symbol")
        .agg(
            trades=("price", "size"),
            avg_trade_price=("price", "mean"),
            avg_qty=("quantity", "mean"),
            avg_rel_mid=("rel_mid", "mean"),
            rel_mid_std=("rel_mid", "std"),
            buy_share=("side", lambda s: (s == "buy").mean()),
            sell_share=("side", lambda s: (s == "sell").mean()),
            inside_share=("side", lambda s: (s == "inside").mean()),
        )
        .round(4)
    )
    return out


def plot_mid_paths(df: pd.DataFrame, title: str):
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    for ax, product in zip(axes, PRODUCTS):
        sub = clean_mid(df, product)
        code = SHORT[product]
        ax.plot(sub["t"], sub["mid_price"], color=COLORS[code], lw=0.7)
        for boundary in sorted(df["day"].unique())[1:]:
            ax.axvline(boundary * 1_000_000, color="black", ls="--", alpha=0.35)
        ax.set_title(f"{code} mid-price")
        ax.set_ylabel("mid")
    axes[-1].set_xlabel("global time = day * 1_000_000 + timestamp")
    fig.suptitle(title, y=1.02)
    plt.tight_layout()
    plt.show()


def plot_spread_depth(df: pd.DataFrame):
    fig, axes = plt.subplots(2, 2, figsize=(13, 7))
    for col_idx, product in enumerate(PRODUCTS):
        sub = clean_mid(df, product)
        code = SHORT[product]
        axes[0, col_idx].hist(sub["spread"], bins=30, color=COLORS[code], alpha=0.8)
        axes[0, col_idx].set_title(f"{code} spread distribution")
        axes[1, col_idx].hist(sub["depth_top"], bins=35, color=COLORS[code], alpha=0.8)
        axes[1, col_idx].set_title(f"{code} top-of-book depth")
    plt.tight_layout()
    plt.show()


def plot_ipr_formula(df: pd.DataFrame):
    sub, beta = ipr_trend_fit(df)
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(sub["t"], sub["mid_price"], label="mid", lw=0.7, color=COLORS["IPR"])
    axes[0].plot(sub["t"], sub["fair_formula"], label="fit", lw=1.0, color="black", alpha=0.8)
    axes[0].legend()
    axes[0].set_title("IPR mid-price vs fitted fair-value formula")
    axes[1].plot(sub["t"], sub["trend_resid"], lw=0.7, color="#2ca02c")
    axes[1].axhline(0, color="black", lw=1)
    axes[1].set_title("IPR residual around formula")
    axes[1].set_xlabel("global time")
    plt.tight_layout()
    plt.show()
    return beta
"""


ROUND2_EDA_NOTEBOOK = {
    "cells": [
        md(
            """
            # Round 2 EDA

            Deep-dive notebook for the `ROUND_2/` dataset. The goal is to answer four practical questions:

            1. What structural regimes still dominate the two products?
            2. How different is Round 2 from the Round 1 baseline?
            3. Which order-book signals remain predictive after accounting for spread and drift?
            4. What is likely useful for strategy design versus what is just descriptive noise?
            """
        ),
        code(COMMON_HELPERS),
        md(
            """
            ## Load Round 1 and Round 2

            Round 1 is kept here only as a baseline. The rest of the notebook is centered on `ROUND_2/`.
            """
        ),
        code(
            """
            prices_round1, trades_round1 = load_round(ROUND1_DIR, 1)
            prices_round2, trades_round2 = load_round(ROUND2_DIR, 2)

            prices_round1 = prepare_features(prices_round1)
            prices_round2 = prepare_features(prices_round2)

            print("Round 1 prices:", prices_round1.shape, "| trades:", trades_round1.shape)
            print("Round 2 prices:", prices_round2.shape, "| trades:", trades_round2.shape)
            print("Round 2 days:", sorted(prices_round2["day"].unique()))
            print("Round 2 products:", sorted(prices_round2["product"].unique()))
            """
        ),
        md("## Round 2 data quality and order-book shape"),
        code("quality_table(prices_round2)"),
        code("plot_mid_paths(prices_round2, title='Round 2 mid-price paths')"),
        code("plot_spread_depth(prices_round2)"),
        md(
            """
            ## Regime fit

            `ASH_COATED_OSMIUM` is tested as a stationary OU-style process.

            `INTARIAN_PEPPER_ROOT` is modeled directly as a deterministic linear function of `day` and `timestamp`:

            `fair(day, timestamp) = a + b * day + c * timestamp`
            """
        ),
        code("regime_table(prices_round2)"),
        code(
            """
            beta = plot_ipr_formula(prices_round2)
            print(
                f"Fitted IPR fair formula: {beta[0]:.3f} + {beta[1]:.6f} * day + {beta[2]:.9f} * timestamp"
            )
            """
        ),
        md("## Round 1 vs Round 2 parameter comparison"),
        code("compare_rounds(prices_round1, prices_round2)"),
        md(
            """
            ## Signal quality by horizon

            The tables below use raw future mid-price change as the target markout. This is not net PnL.

            That distinction matters:

            - strong raw markout can still be untradable after paying the spread;
            - signals below half-spread are better used for quote skew, fair-value adjustment, or inventory leaning;
            - signals above half-spread become plausible candidates for selective aggression.
            """
        ),
        code(
            """
            print("ACO signal correlations to future mid moves")
            display_aco = horizon_signal_table(prices_round2, "ASH_COATED_OSMIUM")
            print(display_aco)

            print("\\nIPR signal correlations to future mid moves")
            display_ipr = horizon_signal_table(prices_round2, "INTARIAN_PEPPER_ROOT")
            print(display_ipr)
            """
        ),
        code(
            """
            print("ACO imbalance bucketed markouts -> 10-tick markout")
            print(markout_table(prices_round2, "ASH_COATED_OSMIUM", "imbalance", horizon=10))

            print("\\nACO rolling z-score quintiles -> 10-tick markout")
            print(markout_table(prices_round2, "ASH_COATED_OSMIUM", "price_z", horizon=10))

            print("\\nIPR trend-residual z-score quintiles -> 10-tick markout")
            print(markout_table(prices_round2, "INTARIAN_PEPPER_ROOT", "trend_z", horizon=10))
            """
        ),
        code(
            """
            print("ACO threshold markouts")
            print(threshold_markouts(prices_round2, "ASH_COATED_OSMIUM", horizon=10))

            print("\\nIPR threshold markouts")
            print(threshold_markouts(prices_round2, "INTARIAN_PEPPER_ROOT", horizon=10))
            """
        ),
        md("## Trade tape alignment"),
        code(
            """
            aligned_round2 = align_trades_to_book(prices_round2, trades_round2)
            trade_summary(aligned_round2)
            """
        ),
        md(
            """
            ## Interpretation

            The recurring pattern is:

            - `ASH_COATED_OSMIUM`: stationary around ~10,001 with a short half-life and strong L1 imbalance signal. This still looks like a quote-skew / inventory-management product more than a pure taker product.
            - `INTARIAN_PEPPER_ROOT`: the deterministic day-plus-time trend remains the main edge, and the residual around that trend is still bounded enough to fade selectively.
            - Round 2 did not break the Round 1 structure. The main changes are quantitative, not qualitative: slightly higher pepper residual noise, wider pepper spreads, and more osmium trading activity.
            """
        ),
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


ROUND2_FINDINGS = dedent(
    """
    # Round 2 Findings

    Analysis source: `ROUND_2/prices_round_2_day_{-1,0,1}.csv` and `ROUND_2/trades_round_2_day_{-1,0,1}.csv`.

    ## Executive summary

    Round 2 preserves the same core market structure as Round 1:

    - `ASH_COATED_OSMIUM` is still a tight mean-reversion / market-making product centered around roughly `10,001`.
    - `INTARIAN_PEPPER_ROOT` still follows an almost deterministic upward fair-value path with bounded residual noise.
    - The main Round 2 changes are quantitative rather than qualitative: pepper spreads are wider, pepper residual noise is slightly larger, and osmium trade count is higher.

    ## Dataset structure

    - 60,000 price rows total: 3 days x 2 products x 10,000 order-book snapshots.
    - 2,391 trade rows total.
    - Timestamp grid still runs from `0` to `999900` in 100-unit steps inside each day.
    - Counterparty tags are still unusable: `buyer` and `seller` are entirely missing.
    - Only about `0.17%` of price rows have `mid_price == 0`; these are thin-book rows and should be filtered before fitting or signal work.

    ## Product 1: ASH_COATED_OSMIUM

    Key metrics from clean rows:

    - Fair value: about `10000.88`
    - Mid-price sigma: about `5.10`
    - Mean spread: about `16.23`
    - OU AR(1) phi: about `0.739`
    - OU half-life: about `2.29` ticks
    - Lag-1 return autocorrelation: about `-0.50`

    Interpretation:

    - This is still a classic short-half-life reversion product.
    - The raw reversion speed is strong, but the spread is large enough that blind aggressive mean reversion is not obviously attractive.
    - The better use case is quote placement, skewing, and inventory management around a stable fair value.

    Signal findings:

    - L1 imbalance remains strong. At a 10-tick horizon, imbalance correlation to future mid move is about `0.63`.
    - Conditioning on imbalance magnitude matters:
      - imbalance `>= 0.50`: average 10-tick markout about `+6.34`
      - imbalance `<= -0.50`: average 10-tick markout about `-6.35`
    - A rolling z-score of mid around its local mean still mean-reverts:
      - z `<= -1.5`: average 10-tick markout about `+5.42`
      - z `>= +1.5`: average 10-tick markout about `-5.55`

    Practical conclusion:

    - Use imbalance and short-horizon deviation as skew signals, not as automatic crossing signals.
    - With a half-spread around `8`, these markouts are useful for improving passive quotes and leaning inventory rather than paying the spread every time.

    ## Product 2: INTARIAN_PEPPER_ROOT

    The dominant Round 2 edge is still the deterministic fair-value drift. A fitted linear model on clean rows gives:

    `fair(day, timestamp) ~= 11999.970 + 999.985 * day + 0.001000006 * timestamp`

    In practical terms, this is effectively:

    `fair(day, timestamp) ~= 12000 + 1000 * day + 0.001 * timestamp`

    Key metrics:

    - Mean spread: about `14.12`
    - Spread by day: `13.07 -> 14.12 -> 15.18`
    - Residual sigma around the fitted fair value: about `2.37`
    - Residual range: about `[-11.35, +11.34]`
    - Residual AR(1): about `0.009`
    - Residual half-life: essentially zero

    Interpretation:

    - The level process looks non-stationary only because the fair value itself is rising almost mechanically.
    - After detrending, the residual is near-white-noise with tight bounds.
    - That makes pepper a fair-value tracking problem, not a generic momentum or book-pressure problem.

    Signal findings:

    - Trend residual is still the cleanest signal.
    - At a 10-tick horizon:
      - residual `<= -1 sigma`: average markout about `+7.56`
      - residual `>= +1 sigma`: average markout about `-5.49`
      - residual `<= -2 sigma`: average markout about `+7.92`
      - residual `>= +2 sigma`: average markout about `-5.79`
    - L1 imbalance is also predictive, with about `0.65` correlation to 10-tick future mid move.

    Practical conclusion:

    - The cleanest pepper framework is:
      1. compute deterministic fair value from day and timestamp,
      2. maintain a structural long bias because fair value rises through the day,
      3. use negative residuals as higher-conviction buy zones,
      4. fade large positive residuals selectively, especially if inventory is already long.

    ## Round 1 vs Round 2 comparison

    The regime did not change:

    - Osmium remains stationary and mean-reverting.
    - Pepper remains deterministic-trending with bounded residuals.

    The main deltas:

    - `ASH_COATED_OSMIUM`
      - fair value shifted slightly upward from about `10000.20` to about `10000.88`
      - half-life shortened from about `2.49` ticks to about `2.29` ticks
      - spread stayed basically unchanged around `16.2`
      - trades/day increased from roughly `420` to roughly `465`
    - `INTARIAN_PEPPER_ROOT`
      - time slope stayed effectively identical at `~0.001`
      - residual sigma rose from about `2.20` to about `2.37`
      - spread widened by roughly `1` tick across the whole round profile
      - trade count stayed flat around `332` per day

    ## Strategy implications

    - `ASH_COATED_OSMIUM`
      - build around passive market making
      - anchor fair value near `10,001`
      - skew quote placement with imbalance and short-horizon z-score
      - avoid overpaying spread for small raw markouts
    - `INTARIAN_PEPPER_ROOT`
      - treat the deterministic fair-value formula as the primary state variable
      - keep a long inventory bias whenever risk limits allow
      - buy negative residuals aggressively relative to positive residuals
      - be aware that widening spread reduces the attractiveness of short holding-period aggression

    ## Cautions

    - All markouts above are raw future mid moves, not realized PnL.
    - Counterparty tags are unavailable, so there is no reliable informed-flow segmentation.
    - Pepper still trends strongly, but the per-10-tick drift is only about `+1`, which is much smaller than the spread. Pure aggression needs either longer holding periods or residual dislocation on top of the base trend.
    """
).strip() + "\n"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    write_json(ROOT / "round2_eda.ipynb", ROUND2_EDA_NOTEBOOK)
    (ROOT / "round2_findings.md").write_text(ROUND2_FINDINGS, encoding="utf-8")


if __name__ == "__main__":
    main()
