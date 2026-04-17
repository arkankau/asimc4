"""
Backtester for IMC Prosperity 4.

Usage:
    # Run on a specific round directory
    python backtest.py --round ROUND1

    # Run on specific day files
    python backtest.py --files ROUND1/prices_round_1_day_0.csv

    # Run a specific strategy version
    python backtest.py --round ROUND1 --strategy strategies/v1/trader.py
"""
import csv
import sys
import os
import importlib.util
import argparse
from datamodel import OrderDepth, TradingState, Order, Listing, Observation

POSITION_LIMIT = 80


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_price_file(filepath: str) -> dict:
    """Returns {timestamp: {product: OrderDepth}} from a prices CSV."""
    data = {}
    with open(filepath) as f:
        for row in csv.DictReader(f, delimiter=';'):
            mid = row.get('mid_price', '')
            if not mid or mid == '0.0':
                continue
            t = int(row['timestamp'])
            product = row['product']
            od = OrderDepth()
            for i in range(1, 4):
                bp = row.get(f'bid_price_{i}')
                bv = row.get(f'bid_volume_{i}')
                ap = row.get(f'ask_price_{i}')
                av = row.get(f'ask_volume_{i}')
                if bp and bv:
                    od.buy_orders[int(float(bp))] = int(float(bv))
                if ap and av:
                    od.sell_orders[int(float(ap))] = -int(float(av))
            data.setdefault(t, {})[product] = od
    return data


def find_price_files(round_dir: str) -> list:
    """Returns sorted list of prices_*.csv paths in a round directory."""
    files = [
        os.path.join(round_dir, f)
        for f in sorted(os.listdir(round_dir))
        if f.startswith('prices_') and f.endswith('.csv')
    ]
    return files


# ---------------------------------------------------------------------------
# Exchange matching
# ---------------------------------------------------------------------------

def match_orders(orders: list, order_depth: OrderDepth, position: int) -> tuple:
    """
    Matches player orders against the bot order book (immediate fills only).
    Returns (cash_delta, position_delta, filled_orders).
    Resting orders that bots hit are NOT simulated here.
    """
    cash = 0
    pos = position

    buy_orders = sorted([o for o in orders if o.quantity > 0], key=lambda o: -o.price)
    sell_orders = sorted([o for o in orders if o.quantity < 0], key=lambda o: o.price)

    for order in buy_orders:
        remaining = order.quantity
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price > order.price or remaining <= 0:
                break
            capacity = POSITION_LIMIT - pos
            if capacity <= 0:
                break
            fill = min(remaining, -order_depth.sell_orders[ask_price], capacity)
            cash -= fill * ask_price
            pos += fill
            remaining -= fill

    for order in sell_orders:
        remaining = -order.quantity
        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price < order.price or remaining <= 0:
                break
            capacity = POSITION_LIMIT + pos
            if capacity <= 0:
                break
            fill = min(remaining, order_depth.buy_orders[bid_price], capacity)
            cash += fill * bid_price
            pos -= fill
            remaining -= fill

    return cash, pos - position


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_file(price_file: str, trader, initial_position: dict = None) -> dict:
    """
    Runs one price file through the trader.
    Returns {product: {pnl, final_position, trades}} and total cash.
    Carries initial_position forward if provided (for multi-day sims).
    """
    data = load_price_file(price_file)
    timestamps = sorted(data.keys())

    position = dict(initial_position) if initial_position else {}
    cash_by_product = {}
    trade_count = {}
    trader_data = ""

    for t in timestamps:
        order_depths = data[t]
        listings = {p: Listing(p, p, "XIRECS") for p in order_depths}
        state = TradingState(
            traderData=trader_data,
            timestamp=t,
            listings=listings,
            order_depths=order_depths,
            own_trades={},
            market_trades={},
            position=dict(position),
            observations=Observation({}, {}),
        )

        result, _, trader_data = trader.run(state)

        for product, orders in result.items():
            od = order_depths.get(product)
            if not od:
                continue
            pos = position.get(product, 0)
            cash_delta, pos_delta = match_orders(orders, od, pos)
            position[product] = pos + pos_delta
            cash_by_product[product] = cash_by_product.get(product, 0) + cash_delta
            if pos_delta != 0:
                trade_count[product] = trade_count.get(product, 0) + abs(pos_delta)

    # Mark-to-market at last timestamp
    last_od = data[timestamps[-1]]
    total_cash = sum(cash_by_product.values())
    for product, pos in position.items():
        if pos == 0:
            continue
        od = last_od.get(product)
        if not od:
            continue
        if od.buy_orders and od.sell_orders:
            mid = (max(od.buy_orders) + min(od.sell_orders)) / 2
        elif od.buy_orders:
            mid = max(od.buy_orders)
        elif od.sell_orders:
            mid = min(od.sell_orders)
        else:
            continue
        mtm = pos * mid
        cash_by_product[product] = cash_by_product.get(product, 0) + mtm
        total_cash += mtm

    return {
        'file': price_file,
        'position': position,
        'cash_by_product': cash_by_product,
        'trade_count': trade_count,
        'total': total_cash,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_result(result: dict):
    print(f"\n  File: {os.path.basename(result['file'])}")
    products = sorted(set(list(result['cash_by_product'].keys()) + list(result['position'].keys())))
    for p in products:
        pnl = result['cash_by_product'].get(p, 0)
        pos = result['position'].get(p, 0)
        trades = result['trade_count'].get(p, 0)
        print(f"    {p:<30s}  P&L={pnl:>10,.0f}  pos={pos:>+4d}  volume={trades}")
    print(f"    {'TOTAL':<30s}  P&L={result['total']:>10,.0f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def load_trader(strategy_path: str = None):
    if strategy_path:
        spec = importlib.util.spec_from_file_location("trader", strategy_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.Trader()
    from trader import Trader
    return Trader()


def main():
    parser = argparse.ArgumentParser(description="Prosperity 4 backtester")
    parser.add_argument('--round', help='Round directory (e.g. ROUND1)')
    parser.add_argument('--files', nargs='+', help='Specific price CSV files')
    parser.add_argument('--strategy', help='Path to trader.py (default: ./trader.py)')
    args = parser.parse_args()

    trader = load_trader(args.strategy)

    if args.files:
        price_files = args.files
    elif args.round:
        price_files = find_price_files(args.round)
    else:
        # Default: run all rounds found in current directory
        price_files = []
        for d in sorted(os.listdir('.')):
            if os.path.isdir(d) and d.startswith('ROUND'):
                price_files.extend(find_price_files(d))

    if not price_files:
        print("No price files found.")
        sys.exit(1)

    print(f"Running backtest with: {args.strategy or 'trader.py'}")
    grand_total = 0
    for f in price_files:
        result = simulate_file(f, trader)
        print_result(result)
        grand_total += result['total']

    if len(price_files) > 1:
        print(f"\n  {'GRAND TOTAL':<30s}  P&L={grand_total:>10,.0f}")


if __name__ == "__main__":
    main()
