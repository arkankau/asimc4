from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

Time = int
Symbol = str
Product = str
Position = int
UserId = str
ObservationValue = int


@dataclass
class Listing:
    symbol: Symbol
    product: Product
    denomination: Product


@dataclass
class ConversionObservation:
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sunlight: float = 0.0
    humidity: float = 0.0


@dataclass
class Observation:
    plainValueObservations: dict[Product, ObservationValue] = field(default_factory=dict)
    conversionObservations: dict[Product, ConversionObservation] = field(default_factory=dict)


@dataclass
class Order:
    symbol: Symbol
    price: int
    quantity: int


@dataclass
class OrderDepth:
    buy_orders: dict[int, int] = field(default_factory=dict)
    sell_orders: dict[int, int] = field(default_factory=dict)


@dataclass
class Trade:
    symbol: Symbol
    price: int
    quantity: int
    buyer: UserId
    seller: UserId
    timestamp: Time


@dataclass
class TradingState:
    traderData: str
    timestamp: Time
    listings: dict[Symbol, Listing]
    order_depths: dict[Symbol, OrderDepth]
    own_trades: dict[Symbol, list[Trade]]
    market_trades: dict[Symbol, list[Trade]]
    position: dict[Product, Position]
    observations: Observation


class ProsperityEncoder(json.JSONEncoder):
    """Small compatibility shim for strategies that dump IMC objects to JSON."""

    def default(self, obj: Any) -> Any:
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)

        return super().default(obj)

