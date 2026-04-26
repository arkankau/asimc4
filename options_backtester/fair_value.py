from __future__ import annotations

import math
from dataclasses import dataclass

from imc_backtester.log_parser import PriceSnapshot

UNDERLYING = "VELVETFRUIT_EXTRACT"
IMPLIED_VOL_MAX = 3.0
VEGA_FLOOR = 0.25
MIN_FIT_POINTS = 3
ANCHOR_STRIKE_MIN = 5000
ANCHOR_STRIKE_MAX = 5500


@dataclass(frozen=True)
class VoucherDiagnostics:
    product: str
    strike: int | None
    used_in_fit: bool
    raw_mid: float
    signal_mark: float
    inventory_mark: float
    liquidation_mark: float
    raw_iv: float | None
    fitted_iv: float | None
    delta: float | None
    vega: float | None
    theta: float | None
    price_residual: float | None
    repair_flags: tuple[str, ...]


@dataclass(frozen=True)
class FairValueSnapshot:
    signal_marks: dict[str, float]
    inventory_marks: dict[str, float]
    liquidation_marks: dict[str, float]
    diagnostics: dict[str, VoucherDiagnostics]


def _parse_voucher_strike(symbol: str) -> int | None:
    if not symbol.startswith("VEV_"):
        return None
    suffix = symbol[4:]
    return int(suffix) if suffix.isdigit() else None


def _best_bid(snapshot: PriceSnapshot) -> int | None:
    return snapshot.bid_prices[0] if snapshot.bid_prices else None


def _best_ask(snapshot: PriceSnapshot) -> int | None:
    return snapshot.ask_prices[0] if snapshot.ask_prices else None


def _base_mark(snapshot: PriceSnapshot, previous_mark: float) -> float:
    if snapshot.mid_price > 0:
        return float(snapshot.mid_price)

    best_bid = _best_bid(snapshot)
    best_ask = _best_ask(snapshot)
    if best_bid is not None and best_ask is not None:
        return 0.5 * (best_bid + best_ask)

    return previous_mark


def _spread(snapshot: PriceSnapshot) -> float | None:
    best_bid = _best_bid(snapshot)
    best_ask = _best_ask(snapshot)
    if best_bid is None or best_ask is None:
        return None
    return float(best_ask - best_bid)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bs_call_price(spot: float, strike: float, tte: float, sigma: float) -> float:
    intrinsic = max(spot - strike, 0.0)
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return intrinsic

    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * _norm_cdf(d1) - strike * _norm_cdf(d2)


def _bs_delta(spot: float, strike: float, tte: float, sigma: float) -> float | None:
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return None
    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    return _norm_cdf(d1)


def _bs_vega(spot: float, strike: float, tte: float, sigma: float) -> float:
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return 0.0
    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    return spot * _norm_pdf(d1) * math.sqrt(tte)


def _bs_theta(spot: float, strike: float, tte: float, sigma: float) -> float | None:
    if tte <= 0.0 or sigma <= 1e-6 or spot <= 0.0 or strike <= 0.0:
        return None
    vol_sqrt_t = sigma * math.sqrt(tte)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte) / vol_sqrt_t
    return -(spot * _norm_pdf(d1) * sigma) / (2.0 * math.sqrt(tte))


def _implied_vol(price: float, spot: float, strike: float, tte: float, sigma_init: float = 0.25) -> float | None:
    intrinsic = max(spot - strike, 0.0)
    if tte <= 0.0 or spot <= 0.0 or strike <= 0.0:
        return None
    if price <= intrinsic + 0.5:
        return None

    sigma = min(IMPLIED_VOL_MAX, max(0.02, sigma_init))
    for _ in range(20):
        model = _bs_call_price(spot, strike, tte, sigma)
        vega = _bs_vega(spot, strike, tte, sigma)
        if vega < VEGA_FLOOR:
            return None
        step = (model - price) / vega
        sigma = min(IMPLIED_VOL_MAX, max(0.02, sigma - step))
        if abs(step) < 1e-5:
            break

    if _bs_vega(spot, strike, tte, sigma) < VEGA_FLOOR:
        return None
    return sigma


def _fit_weighted_quadratic(points: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    if len(points) < MIN_FIT_POINTS:
        return None

    s0 = s1 = s2 = s3 = s4 = 0.0
    t0 = t1 = t2 = 0.0
    for x, y, w in points:
        weight = max(1e-6, w)
        x2 = x * x
        s0 += weight
        s1 += weight * x
        s2 += weight * x2
        s3 += weight * x2 * x
        s4 += weight * x2 * x2
        t0 += weight * y
        t1 += weight * x * y
        t2 += weight * x2 * y

    matrix = [
        [s0, s1, s2, t0],
        [s1, s2, s3, t1],
        [s2, s3, s4, t2],
    ]

    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(matrix[row][col]))
        if abs(matrix[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            matrix[col], matrix[pivot] = matrix[pivot], matrix[col]

        pivot_value = matrix[col][col]
        for idx in range(col, 4):
            matrix[col][idx] /= pivot_value

        for row in range(3):
            if row == col:
                continue
            factor = matrix[row][col]
            for idx in range(col, 4):
                matrix[row][idx] -= factor * matrix[col][idx]

    return matrix[0][3], matrix[1][3], matrix[2][3]


def _select_anchor_products(
    snapshots: dict[str, PriceSnapshot],
    mids: dict[str, float],
    raw_ivs: dict[str, float | None],
    tte_years: float,
    spot: float,
) -> set[str]:
    anchors: set[str] = set()
    fallback: list[tuple[str, float]] = []

    for product, snapshot in snapshots.items():
        strike = _parse_voucher_strike(product)
        raw_iv = raw_ivs.get(product)
        if strike is None or raw_iv is None:
            continue
        vega = _bs_vega(spot, float(strike), tte_years, raw_iv)
        if vega < VEGA_FLOOR:
            continue

        spread = _spread(snapshot)
        fallback.append((product, vega))
        if ANCHOR_STRIKE_MIN <= strike <= ANCHOR_STRIKE_MAX and mids[product] > 1.0 and spread is not None and spread <= 12.0:
            anchors.add(product)

    if len(anchors) >= MIN_FIT_POINTS:
        return anchors

    ordered = [product for product, _vega in sorted(fallback, key=lambda item: item[1], reverse=True)]
    return set(ordered[: max(MIN_FIT_POINTS, len(anchors))])


def build_fair_value_snapshot(
    *,
    snapshots: dict[str, PriceSnapshot],
    previous_marks: dict[str, float],
    positions: dict[str, int],
    expiry_days_at_start: float,
    global_timestamp: int,
) -> FairValueSnapshot:
    signal_marks = {product: _base_mark(snapshot, previous_marks.get(product, 0.0)) for product, snapshot in snapshots.items()}
    inventory_marks = dict(signal_marks)
    liquidation_marks = dict(signal_marks)
    diagnostics: dict[str, VoucherDiagnostics] = {}

    tte_years = max(0.0, expiry_days_at_start - global_timestamp / 1_000_000.0) / 252.0
    spot = signal_marks.get(UNDERLYING, 0.0)

    raw_ivs: dict[str, float | None] = {}
    if spot > 0.0 and tte_years > 0.0:
        for product, mid in signal_marks.items():
            strike = _parse_voucher_strike(product)
            if strike is None:
                continue
            raw_ivs[product] = _implied_vol(mid, spot, float(strike), tte_years)

        anchors = _select_anchor_products(snapshots, signal_marks, raw_ivs, tte_years, spot)
        fit_points = []
        for product in anchors:
            strike = _parse_voucher_strike(product)
            raw_iv = raw_ivs.get(product)
            if strike is None or raw_iv is None:
                continue
            moneyness = math.log(spot / float(strike))
            vega = _bs_vega(spot, float(strike), tte_years, raw_iv)
            fit_points.append((moneyness, raw_iv, vega))

        coeffs = _fit_weighted_quadratic(fit_points)
        if coeffs is not None:
            a0, a1, a2 = coeffs
            for product in list(signal_marks):
                strike = _parse_voucher_strike(product)
                if strike is None:
                    continue
                moneyness = math.log(spot / float(strike))
                fitted_iv = max(0.05, min(IMPLIED_VOL_MAX, a0 + a1 * moneyness + a2 * moneyness * moneyness))
                signal_marks[product] = _bs_call_price(spot, float(strike), tte_years, fitted_iv)

    for product, snapshot in snapshots.items():
        best_bid = _best_bid(snapshot)
        best_ask = _best_ask(snapshot)
        position = positions.get(product, 0)
        signal_mark = signal_marks[product]
        if position > 0 and best_bid is not None:
            inventory_marks[product] = float(best_bid)
            spread = (_spread(snapshot) or 0.0) / 2.0
            liquidation_marks[product] = max(0.0, signal_mark - max(0.5, spread))
        elif position < 0 and best_ask is not None:
            inventory_marks[product] = float(best_ask)
            spread = (_spread(snapshot) or 0.0) / 2.0
            liquidation_marks[product] = signal_mark + max(0.5, spread)
        else:
            inventory_marks[product] = signal_mark
            liquidation_marks[product] = signal_mark

    repair_flags: dict[str, set[str]] = {product: set() for product in snapshots}
    ordered_vouchers = sorted(
        (product for product in snapshots if _parse_voucher_strike(product) is not None),
        key=lambda product: _parse_voucher_strike(product) or 0,
    )
    for left, right in zip(ordered_vouchers[:-1], ordered_vouchers[1:]):
        left_strike = _parse_voucher_strike(left)
        right_strike = _parse_voucher_strike(right)
        if left_strike is None or right_strike is None:
            continue
        left_mid = signal_marks[left]
        right_mid = signal_marks[right]
        spread_price = left_mid - right_mid
        if spread_price < -0.5 or spread_price > (right_strike - left_strike) + 0.5:
            repair_flags[left].add("vertical_spread_monotonicity")
            repair_flags[right].add("vertical_spread_monotonicity")

    for product, snapshot in snapshots.items():
        strike = _parse_voucher_strike(product)
        raw_mid = _base_mark(snapshot, previous_marks.get(product, 0.0))
        raw_iv = raw_ivs.get(product)
        fitted_iv = None
        delta = None
        vega = None
        theta = None
        price_residual = None
        used_in_fit = False

        if strike is not None and spot > 0.0 and tte_years > 0.0:
            fitted_iv = _implied_vol(signal_marks[product], spot, float(strike), tte_years)
            delta = _bs_delta(spot, float(strike), tte_years, fitted_iv or 0.0) if fitted_iv is not None else None
            vega = _bs_vega(spot, float(strike), tte_years, fitted_iv or 0.0) if fitted_iv is not None else None
            theta = _bs_theta(spot, float(strike), tte_years, fitted_iv or 0.0) if fitted_iv is not None else None
            price_residual = raw_mid - signal_marks[product]
            used_in_fit = (
                ANCHOR_STRIKE_MIN <= strike <= ANCHOR_STRIKE_MAX
                and raw_iv is not None
                and raw_mid > 1.0
                and (_spread(snapshot) is not None and (_spread(snapshot) or 0.0) <= 12.0)
            )

        diagnostics[product] = VoucherDiagnostics(
            product=product,
            strike=strike,
            used_in_fit=used_in_fit,
            raw_mid=raw_mid,
            signal_mark=signal_marks[product],
            inventory_mark=inventory_marks[product],
            liquidation_mark=liquidation_marks[product],
            raw_iv=raw_iv,
            fitted_iv=fitted_iv,
            delta=delta,
            vega=vega,
            theta=theta,
            price_residual=price_residual,
            repair_flags=tuple(sorted(repair_flags[product])),
        )

    return FairValueSnapshot(
        signal_marks=signal_marks,
        inventory_marks=inventory_marks,
        liquidation_marks=liquidation_marks,
        diagnostics=diagnostics,
    )
