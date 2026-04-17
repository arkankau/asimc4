# IMC Prosperity 4 — API Reference

Source: https://imc-prosperity.notion.site/writing-an-algorithm-in-python

## Trader class structure

```python
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List

class Trader:
    def bid(self):          # Round 2 only; ignored otherwise
        return 15

    def run(self, state: TradingState):
        result = {}         # Dict[product, List[Order]]
        conversions = 0     # int or None
        traderData = ""     # serialized state string (max 50,000 chars)
        return result, conversions, traderData
```

## TradingState properties

| Property | Type | Description |
|---|---|---|
| `traderData` | str | Serialized state from previous iteration |
| `timestamp` | int | Current time step |
| `listings` | Dict[Symbol, Listing] | Available products |
| `order_depths` | Dict[Symbol, OrderDepth] | Bot order books per product |
| `own_trades` | Dict[Symbol, List[Trade]] | Own trades since last state |
| `market_trades` | Dict[Symbol, List[Trade]] | Other participants' trades |
| `position` | Dict[Product, int] | Current positions (signed) |
| `observations` | Observation | Plain values + ConversionObservations |

## OrderDepth

```python
order_depth.buy_orders   # Dict[price, qty]  — qty positive
order_depth.sell_orders  # Dict[price, qty]  — qty NEGATIVE
```

Best ask = `min(sell_orders.keys())`, best bid = `max(buy_orders.keys())`

## Order

```python
Order(symbol, price, quantity)
# quantity > 0 → BUY, quantity < 0 → SELL
```

## Position limits

- Absolute limit: |position| ≤ limit at all times
- If aggregated buy (sell) orders would breach limit, **all orders for that product are rejected**
- Available capacity: `limit - current_position` (buys), `limit + current_position` (sells)

## ConversionObservation (for conversion products)

```python
obs.bidPrice, obs.askPrice       # conversion prices
obs.transportFees                # always paid
obs.exportTariff / importTariff  # directional
```

Cost to import (buy via conversion): `askPrice + transportFees + importTariff`
Cost to export (sell via conversion): `bidPrice - transportFees - exportTariff`

## State persistence

Use `jsonpickle` to serialize/deserialize `traderData`:
```python
import jsonpickle
state_dict = jsonpickle.decode(state.traderData) if state.traderData else {}
# ... mutate state_dict ...
traderData = jsonpickle.encode(state_dict)
```

## Supported libraries

pandas, numpy, statistics, math, typing, jsonpickle + all Python 3.12 stdlib
