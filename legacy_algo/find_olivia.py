"""
Hunt for 'Olivia'-style informed trades: buys at running daily low, sells at running daily high.
Trader IDs are NaN in Round 1 data, so we infer by behavior + size signature.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).parent / "ROUND1"
DAYS = [-2, -1, 0]
PRODUCTS = ["ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"]


def load():
    prices = pd.concat(
        [pd.read_csv(ROOT / f"prices_round_1_day_{d}.csv", sep=";").assign(day=d) for d in DAYS],
        ignore_index=True,
    )
    trades = pd.concat(
        [pd.read_csv(ROOT / f"trades_round_1_day_{d}.csv", sep=";").assign(day=d) for d in DAYS],
        ignore_index=True,
    )
    return prices, trades


def aggressor_side(trades, prices):
    """Tag each trade as BUY/SELL aggressor by comparing price to mid at that tick."""
    mid = prices.set_index(["day", "timestamp", "product"])["mid_price"]
    trades = trades.copy()
    trades["mid"] = trades.apply(
        lambda r: mid.get((r["day"], r["timestamp"], r["symbol"]), np.nan), axis=1
    )
    trades["aggressor"] = np.where(
        trades["price"] > trades["mid"], "BUY",
        np.where(trades["price"] < trades["mid"], "SELL", "MID"),
    )
    return trades


def find_extrema_trades(trades, prices, product, tol=1.0):
    """An 'extremal' trade is an aggressive buy when MID is near running daily low,
    or an aggressive sell when MID is near running daily high."""
    out = []
    for day in DAYS:
        p = prices[(prices["day"] == day) & (prices["product"] == product)].sort_values("timestamp")
        t = trades[(trades["day"] == day) & (trades["symbol"] == product)].sort_values("timestamp")
        if p.empty or t.empty:
            continue
        p = p.assign(run_min=p["mid_price"].cummin(), run_max=p["mid_price"].cummax())
        lookup = p.set_index("timestamp")[["mid_price", "run_min", "run_max"]]
        for _, r in t.iterrows():
            if r["timestamp"] not in lookup.index:
                continue
            mid, rmin, rmax = lookup.loc[r["timestamp"]]
            if pd.isna(mid):
                continue
            mid_at_low  = mid <= rmin + tol
            mid_at_high = mid >= rmax - tol
            if r["aggressor"] == "BUY" and mid_at_low:
                out.append({**r.to_dict(), "signal": "BUY_AT_LOW", "run_min": rmin, "run_max": rmax})
            elif r["aggressor"] == "SELL" and mid_at_high:
                out.append({**r.to_dict(), "signal": "SELL_AT_HIGH", "run_min": rmin, "run_max": rmax})
    return pd.DataFrame(out)


def extremum_count_per_day(prices, product):
    """How often does the running min/max get updated per day? Olivia strikes at NEW extremes."""
    rows = []
    for day in DAYS:
        p = prices[(prices["day"] == day) & (prices["product"] == product)].sort_values("timestamp")
        rmin = p["mid_price"].cummin()
        rmax = p["mid_price"].cummax()
        new_lows  = (rmin.diff() < 0).sum()
        new_highs = (rmax.diff() > 0).sum()
        rows.append({"day": day, "new_lows": new_lows, "new_highs": new_highs,
                     "final_min": rmin.iloc[-1], "final_max": rmax.iloc[-1]})
    return pd.DataFrame(rows)


def size_signature(trades, product):
    """Olivia in P3 had a 15-lot signature. Look at size distribution per product."""
    t = trades[trades["symbol"] == product]
    return t["quantity"].value_counts().sort_index()


def main():
    prices, trades = load()
    trades = aggressor_side(trades, prices)

    print("=" * 72)
    print("Size distribution (find any outlier trader with a fixed size)")
    print("=" * 72)
    for prod in PRODUCTS:
        print(f"\n{prod}:")
        sig = size_signature(trades, prod)
        print(sig.to_string())

    print("\n" + "=" * 72)
    print("How often does a new daily extreme print? (Olivia strikes at NEW extremes)")
    print("=" * 72)
    for prod in PRODUCTS:
        print(f"\n{prod}:")
        print(extremum_count_per_day(prices, prod).to_string(index=False))

    print("\n" + "=" * 72)
    print("Candidate Olivia trades (aggressive when mid is at/near running daily extreme)")
    print("=" * 72)
    for prod in PRODUCTS:
        hits = find_extrema_trades(trades, prices, prod, tol=1.0)
        total = (trades["symbol"] == prod).sum()
        print(f"\n{prod}: {len(hits)} of {total} trades ({100*len(hits)/total:.1f}%)")
        if not hits.empty:
            print("\n  by signal + quantity:")
            print(hits.groupby(["signal", "quantity"]).size().unstack(fill_value=0).to_string())
            print("\n  by signal + day:")
            print(hits.groupby(["signal", "day"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
