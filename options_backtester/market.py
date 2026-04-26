from __future__ import annotations

from pathlib import Path

from imc_backtester.round3_csv_runner import (
    DAY_MODES,
    TIMESTAMP_MODES,
    Round3CsvData,
    _parse_voucher_strike,
    _resolve_timestamp_mode,
    _round3_limits,
    _tte_days,
    build_state,
    load_round3_csv_data,
)

UNDERLYING = "VELVETFRUIT_EXTRACT"


def _is_options_product(product: str) -> bool:
    return product == UNDERLYING or _parse_voucher_strike(product) is not None


def load_options_csv_data(data_dir: Path, days: set[int] | None = None) -> Round3CsvData:
    csv_data = load_round3_csv_data(data_dir, days=days)
    products = [product for product in csv_data.products if _is_options_product(product)]
    allowed = set(products)
    if UNDERLYING not in allowed:
        raise ValueError(f"{UNDERLYING} was not found in {data_dir}")
    if not any(product != UNDERLYING for product in products):
        raise ValueError(f"No VEV voucher products were found in {data_dir}")

    prices = {
        timestamp: {
            product: snapshot
            for product, snapshot in snapshots.items()
            if product in allowed
        }
        for timestamp, snapshots in csv_data.prices.items()
    }
    trade_history = {
        timestamp: {
            product: trades
            for product, trades in trades_by_symbol.items()
            if product in allowed
        }
        for timestamp, trades_by_symbol in csv_data.trade_history.items()
    }

    return Round3CsvData(
        products=products,
        timestamps=csv_data.timestamps,
        prices=prices,
        trade_history=trade_history,
        day_by_global_timestamp=csv_data.day_by_global_timestamp,
        local_timestamp_by_global_timestamp=csv_data.local_timestamp_by_global_timestamp,
    )


__all__ = [
    "DAY_MODES",
    "TIMESTAMP_MODES",
    "UNDERLYING",
    "Round3CsvData",
    "_resolve_timestamp_mode",
    "_round3_limits",
    "_tte_days",
    "build_state",
    "load_options_csv_data",
]
