from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PriceSnapshot:
    day: int
    timestamp: int
    product: str
    bid_prices: list[int]
    bid_volumes: list[int]
    ask_prices: list[int]
    ask_volumes: list[int]
    mid_price: float


@dataclass(frozen=True)
class TapeTrade:
    timestamp: int
    buyer: str
    seller: str
    symbol: str
    currency: str
    price: int
    quantity: int


@dataclass(frozen=True)
class ParsedSubmissionLog:
    submission_id: str | None
    products: list[str]
    day: int
    timestamps: list[int]
    prices: dict[int, dict[str, PriceSnapshot]]
    trade_history: dict[int, dict[str, list[TapeTrade]]]


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    return int(float(cleaned))


def _parse_activities_log(text: str) -> tuple[int, list[str], dict[int, dict[str, PriceSnapshot]]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    prices: dict[int, dict[str, PriceSnapshot]] = {}
    product_order: list[str] = []
    day_value = 0

    for row in reader:
        day_value = int(row["day"])
        timestamp = int(row["timestamp"])
        product = row["product"]

        if product not in product_order:
            product_order.append(product)

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

        snapshot = PriceSnapshot(
            day=day_value,
            timestamp=timestamp,
            product=product,
            bid_prices=bid_prices,
            bid_volumes=bid_volumes,
            ask_prices=ask_prices,
            ask_volumes=ask_volumes,
            mid_price=float(row["mid_price"]),
        )
        prices.setdefault(timestamp, {})[product] = snapshot

    return day_value, product_order, prices


def _parse_trade_history(entries: list[dict], include_submission_trades: bool) -> dict[int, dict[str, list[TapeTrade]]]:
    grouped: dict[int, dict[str, list[TapeTrade]]] = {}

    for raw in entries:
        buyer = raw.get("buyer", "") or ""
        seller = raw.get("seller", "") or ""

        if not include_submission_trades and (buyer == "SUBMISSION" or seller == "SUBMISSION"):
            continue

        trade = TapeTrade(
            timestamp=int(raw["timestamp"]),
            buyer=buyer,
            seller=seller,
            symbol=raw["symbol"],
            currency=raw.get("currency", "") or "",
            price=int(round(float(raw["price"]))),
            quantity=int(raw["quantity"]),
        )
        grouped.setdefault(trade.timestamp, {}).setdefault(trade.symbol, []).append(trade)

    for trades_by_product in grouped.values():
        for trades in trades_by_product.values():
            trades.sort(key=lambda trade: (trade.price, trade.quantity, trade.buyer, trade.seller))

    return grouped


def load_submission_log(path: str | Path, include_submission_trades: bool = True) -> ParsedSubmissionLog:
    file_path = Path(path).expanduser().resolve()
    data = json.loads(file_path.read_text())

    day, products, prices = _parse_activities_log(data["activitiesLog"])
    trade_history = _parse_trade_history(data.get("tradeHistory", []), include_submission_trades)
    timestamps = sorted(prices.keys())

    return ParsedSubmissionLog(
        submission_id=data.get("submissionId"),
        products=products,
        day=day,
        timestamps=timestamps,
        prices=prices,
        trade_history=trade_history,
    )
