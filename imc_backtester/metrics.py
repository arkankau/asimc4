from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
from pathlib import Path
from typing import Any


def _parse_graph_log(text: str) -> list[tuple[int, float]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    points: list[tuple[int, float]] = []

    for row in reader:
        timestamp = row.get("timestamp")
        value = row.get("value")
        if not timestamp or not value:
            continue
        points.append((int(float(timestamp)), float(value)))

    return points


def _parse_activities_log(text: str) -> tuple[list[tuple[int, float]], dict[str, float]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    totals_by_timestamp: dict[int, float] = {}
    product_final_pnl: dict[str, float] = {}

    for row in reader:
        timestamp = int(row["timestamp"])
        product = row["product"]
        pnl = float(row["profit_and_loss"])
        totals_by_timestamp[timestamp] = totals_by_timestamp.get(timestamp, 0.0) + pnl
        product_final_pnl[product] = pnl

    path = sorted(totals_by_timestamp.items())
    return path, product_final_pnl


def _derive_pnl_path(payload: dict[str, Any]) -> tuple[str, list[tuple[int, float]], dict[str, float]]:
    if payload.get("activitiesLog"):
        path, product_final_pnl = _parse_activities_log(payload["activitiesLog"])
        if path:
            return "activitiesLog", path, product_final_pnl

    if payload.get("graphLog"):
        return "graphLog", _parse_graph_log(payload["graphLog"]), {}

    return "none", [], {}


def _quantile(values: list[float], p: float) -> float | None:
    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * p
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return values[lower]

    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def _max_drawdown(points: list[tuple[int, float]]) -> dict[str, float | int | None]:
    if not points:
        return {
            "max_drawdown": None,
            "max_drawdown_start_timestamp": None,
            "max_drawdown_end_timestamp": None,
            "max_drawdown_recovery_timestamp": None,
            "max_drawdown_duration_steps": None,
        }

    peak_value = points[0][1]
    peak_timestamp = points[0][0]
    max_drawdown = 0.0
    trough_timestamp = points[0][0]
    start_timestamp = peak_timestamp

    for timestamp, value in points:
        if value > peak_value:
            peak_value = value
            peak_timestamp = timestamp

        drawdown = peak_value - value
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            trough_timestamp = timestamp
            start_timestamp = peak_timestamp

    recovery_timestamp = None
    if max_drawdown > 0:
        threshold = next(value for timestamp, value in points if timestamp == start_timestamp)
        saw_trough = False
        for timestamp, value in points:
            if timestamp == trough_timestamp:
                saw_trough = True
            if saw_trough and value >= threshold:
                recovery_timestamp = timestamp
                break

    start_index = next((i for i, (timestamp, _) in enumerate(points) if timestamp == start_timestamp), None)
    end_index = next((i for i, (timestamp, _) in enumerate(points) if timestamp == trough_timestamp), None)
    duration_steps = (end_index - start_index) if start_index is not None and end_index is not None else None

    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_start_timestamp": start_timestamp,
        "max_drawdown_end_timestamp": trough_timestamp,
        "max_drawdown_recovery_timestamp": recovery_timestamp,
        "max_drawdown_duration_steps": duration_steps,
    }


def _bootstrap_metrics(
    increments: list[float],
    block_size: int,
    repetitions: int,
    seed: int,
) -> dict[str, float | int | None] | None:
    if repetitions <= 0 or not increments:
        return None

    rng = random.Random(seed)
    sample_length = len(increments)
    terminal_pnls: list[float] = []
    sharpes: list[float] = []
    max_drawdowns: list[float] = []

    for _ in range(repetitions):
        sample: list[float] = []
        while len(sample) < sample_length:
            start = rng.randrange(sample_length)
            for offset in range(block_size):
                sample.append(increments[(start + offset) % sample_length])
                if len(sample) >= sample_length:
                    break

        terminal = sum(sample)
        terminal_pnls.append(terminal)

        mean_step = sum(sample) / len(sample)
        variance = sum((value - mean_step) ** 2 for value in sample) / len(sample)
        std_step = math.sqrt(variance)
        sharpe = (mean_step / std_step * math.sqrt(len(sample))) if std_step > 0 else None
        if sharpe is not None:
            sharpes.append(sharpe)

        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for increment in sample:
            cumulative += increment
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)
        max_drawdowns.append(max_drawdown)

    terminal_pnls.sort()
    sharpes.sort()
    max_drawdowns.sort()

    return {
        "block_size": block_size,
        "repetitions": repetitions,
        "seed": seed,
        "terminal_pnl_p05": _quantile(terminal_pnls, 0.05),
        "terminal_pnl_p50": _quantile(terminal_pnls, 0.50),
        "terminal_pnl_p95": _quantile(terminal_pnls, 0.95),
        "sharpe_like_p05": _quantile(sharpes, 0.05),
        "sharpe_like_p50": _quantile(sharpes, 0.50),
        "sharpe_like_p95": _quantile(sharpes, 0.95),
        "max_drawdown_p05": _quantile(max_drawdowns, 0.05),
        "max_drawdown_p50": _quantile(max_drawdowns, 0.50),
        "max_drawdown_p95": _quantile(max_drawdowns, 0.95),
    }


def _infer_source_type(payload: dict[str, Any], path: Path) -> str:
    if payload.get("round") == "local":
        return "local_replay"
    if path.suffix == ".log":
        return "website_log"
    if path.suffix == ".json":
        return "website_result"
    return "unknown"


def compute_metrics_from_payload(
    payload: dict[str, Any],
    *,
    source_path: str | None = None,
    bootstrap_repetitions: int = 1000,
    bootstrap_block_size: int = 10,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    path_source, pnl_path, product_final_pnl = _derive_pnl_path(payload)
    timestamps = [timestamp for timestamp, _ in pnl_path]
    values = [value for _, value in pnl_path]
    increments = [values[index] - values[index - 1] for index in range(1, len(values))]

    final_pnl = values[-1] if values else None
    reported_profit = float(payload["profit"]) if payload.get("profit") is not None else None
    mean_step_pnl = (sum(increments) / len(increments)) if increments else None

    std_step_pnl = None
    sharpe_like = None
    sortino_like = None
    profit_factor = None
    positive_steps = sum(1 for value in increments if value > 0)
    negative_steps = sum(1 for value in increments if value < 0)
    flat_steps = sum(1 for value in increments if value == 0)
    positive_step_rate = (positive_steps / len(increments)) if increments else None

    if increments:
        variance = sum((value - mean_step_pnl) ** 2 for value in increments) / len(increments)
        std_step_pnl = math.sqrt(variance)
        if std_step_pnl > 0:
            sharpe_like = mean_step_pnl / std_step_pnl * math.sqrt(len(increments))

        downside_square_mean = sum(min(0.0, value) ** 2 for value in increments) / len(increments)
        downside_std = math.sqrt(downside_square_mean)
        if downside_std > 0:
            sortino_like = mean_step_pnl / downside_std * math.sqrt(len(increments))

        gross_profit = sum(value for value in increments if value > 0)
        gross_loss = -sum(value for value in increments if value < 0)
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss

    drawdown_metrics = _max_drawdown(pnl_path)
    max_drawdown = drawdown_metrics["max_drawdown"]
    profit_to_drawdown = (final_pnl / max_drawdown) if final_pnl is not None and max_drawdown not in (None, 0) else None

    abs_product_total = sum(abs(value) for value in product_final_pnl.values())
    if abs_product_total > 0:
        product_abs_share = {product: abs(value) / abs_product_total for product, value in product_final_pnl.items()}
        largest_product_share = max(product_abs_share.values())
        concentration_hhi = sum(share * share for share in product_abs_share.values())
    else:
        product_abs_share = {}
        largest_product_share = None
        concentration_hhi = None

    trade_history = payload.get("tradeHistory")
    submission_trade_count = None
    submission_buy_count = None
    submission_sell_count = None
    submission_buy_volume = None
    submission_sell_volume = None
    if isinstance(trade_history, list):
        submission_trades = [
            trade
            for trade in trade_history
            if trade.get("buyer") == "SUBMISSION" or trade.get("seller") == "SUBMISSION"
        ]
        submission_trade_count = len(submission_trades)
        submission_buy_count = sum(1 for trade in submission_trades if trade.get("buyer") == "SUBMISSION")
        submission_sell_count = sum(1 for trade in submission_trades if trade.get("seller") == "SUBMISSION")
        submission_buy_volume = sum(int(trade.get("quantity", 0)) for trade in submission_trades if trade.get("buyer") == "SUBMISSION")
        submission_sell_volume = sum(int(trade.get("quantity", 0)) for trade in submission_trades if trade.get("seller") == "SUBMISSION")

    monte_carlo = _bootstrap_metrics(
        increments=increments,
        block_size=bootstrap_block_size,
        repetitions=bootstrap_repetitions,
        seed=bootstrap_seed,
    )

    return {
        "source_path": source_path,
        "path_source": path_source,
        "round": payload.get("round"),
        "status": payload.get("status"),
        "submission_id": payload.get("submissionId"),
        "timestamp_count": len(pnl_path),
        "timestamp_start": timestamps[0] if timestamps else None,
        "timestamp_end": timestamps[-1] if timestamps else None,
        "step_count": len(increments),
        "reported_profit": reported_profit,
        "final_pnl": final_pnl,
        "profit_gap_vs_reported": (final_pnl - reported_profit) if final_pnl is not None and reported_profit is not None else None,
        "mean_step_pnl": mean_step_pnl,
        "std_step_pnl": std_step_pnl,
        "sharpe_like": sharpe_like,
        "sortino_like": sortino_like,
        "profit_factor": profit_factor,
        "positive_steps": positive_steps,
        "negative_steps": negative_steps,
        "flat_steps": flat_steps,
        "positive_step_rate": positive_step_rate,
        **drawdown_metrics,
        "profit_to_drawdown": profit_to_drawdown,
        "product_final_pnl": product_final_pnl,
        "product_abs_share": product_abs_share,
        "largest_product_share": largest_product_share,
        "concentration_hhi": concentration_hhi,
        "positions": payload.get("positions"),
        "submission_trade_count": submission_trade_count,
        "submission_buy_count": submission_buy_count,
        "submission_sell_count": submission_sell_count,
        "submission_buy_volume": submission_buy_volume,
        "submission_sell_volume": submission_sell_volume,
        "monte_carlo": monte_carlo,
    }


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def analyze_result_file(
    path: Path,
    *,
    bootstrap_repetitions: int = 1000,
    bootstrap_block_size: int = 10,
    bootstrap_seed: int = 0,
) -> dict[str, Any]:
    payload = load_payload(path)
    metrics = compute_metrics_from_payload(
        payload,
        source_path=str(path),
        bootstrap_repetitions=bootstrap_repetitions,
        bootstrap_block_size=bootstrap_block_size,
        bootstrap_seed=bootstrap_seed,
    )
    metrics["source_type"] = _infer_source_type(payload, path)
    metrics["file_name"] = path.name
    return metrics


def discover_result_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]

    priorities = {".json": 2, ".log": 1}
    selected: dict[str, Path] = {}

    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.name == ".DS_Store":
            continue
        if file_path.suffix not in priorities:
            continue

        key = str(file_path.with_suffix(""))
        current = selected.get(key)
        if current is None or priorities[file_path.suffix] > priorities[current.suffix]:
            selected[key] = file_path

    return sorted(selected.values())


def _format_metric(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _print_single(metrics: dict[str, Any]) -> None:
    print(f"File: {metrics['source_path']}")
    print(f"Type: {metrics['source_type']}")
    print(f"Final PnL: {_format_metric(metrics['final_pnl'])}")
    print(f"Reported Profit: {_format_metric(metrics['reported_profit'])}")
    print(f"Sharpe-like: {_format_metric(metrics['sharpe_like'])}")
    print(f"Sortino-like: {_format_metric(metrics['sortino_like'])}")
    print(f"Max Drawdown: {_format_metric(metrics['max_drawdown'])}")
    print(f"Profit / Drawdown: {_format_metric(metrics['profit_to_drawdown'])}")
    print(f"Positive Step Rate: {_format_metric(metrics['positive_step_rate'])}")
    print(f"Largest Product Share: {_format_metric(metrics['largest_product_share'])}")

    monte_carlo = metrics.get("monte_carlo")
    if monte_carlo:
        print("Monte Carlo:")
        print(f"  terminal pnl p05: {_format_metric(monte_carlo['terminal_pnl_p05'])}")
        print(f"  terminal pnl p50: {_format_metric(monte_carlo['terminal_pnl_p50'])}")
        print(f"  terminal pnl p95: {_format_metric(monte_carlo['terminal_pnl_p95'])}")
        print(f"  sharpe p05: {_format_metric(monte_carlo['sharpe_like_p05'])}")
        print(f"  max drawdown p95: {_format_metric(monte_carlo['max_drawdown_p95'])}")


def _print_batch(metrics_list: list[dict[str, Any]]) -> None:
    headers = [
        ("file", 20),
        ("pnl", 12),
        ("sharpe", 10),
        ("mdd", 12),
        ("pf/dd", 10),
        ("win%", 8),
        ("mc_p05", 12),
    ]

    header_row = " ".join(label.ljust(width) for label, width in headers)
    print(header_row)
    print("-" * len(header_row))

    for metrics in metrics_list:
        monte_carlo = metrics.get("monte_carlo") or {}
        row = [
            str(metrics["file_name"])[:20].ljust(20),
            _format_metric(metrics["final_pnl"]).rjust(12),
            _format_metric(metrics["sharpe_like"]).rjust(10),
            _format_metric(metrics["max_drawdown"]).rjust(12),
            _format_metric(metrics["profit_to_drawdown"]).rjust(10),
            _format_metric((metrics["positive_step_rate"] * 100) if metrics["positive_step_rate"] is not None else None).rjust(8),
            _format_metric(monte_carlo.get("terminal_pnl_p05")).rjust(12),
        ]
        print(" ".join(row))


def _write_csv(metrics_list: list[dict[str, Any]], output_path: Path) -> None:
    fieldnames = [
        "file_name",
        "source_type",
        "final_pnl",
        "reported_profit",
        "sharpe_like",
        "sortino_like",
        "max_drawdown",
        "profit_to_drawdown",
        "positive_step_rate",
        "largest_product_share",
        "submission_trade_count",
        "submission_buy_volume",
        "submission_sell_volume",
        "mc_terminal_pnl_p05",
        "mc_terminal_pnl_p50",
        "mc_terminal_pnl_p95",
        "mc_sharpe_like_p05",
        "mc_max_drawdown_p95",
        "source_path",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for metrics in metrics_list:
            monte_carlo = metrics.get("monte_carlo") or {}
            writer.writerow(
                {
                    "file_name": metrics.get("file_name"),
                    "source_type": metrics.get("source_type"),
                    "final_pnl": metrics.get("final_pnl"),
                    "reported_profit": metrics.get("reported_profit"),
                    "sharpe_like": metrics.get("sharpe_like"),
                    "sortino_like": metrics.get("sortino_like"),
                    "max_drawdown": metrics.get("max_drawdown"),
                    "profit_to_drawdown": metrics.get("profit_to_drawdown"),
                    "positive_step_rate": metrics.get("positive_step_rate"),
                    "largest_product_share": metrics.get("largest_product_share"),
                    "submission_trade_count": metrics.get("submission_trade_count"),
                    "submission_buy_volume": metrics.get("submission_buy_volume"),
                    "submission_sell_volume": metrics.get("submission_sell_volume"),
                    "mc_terminal_pnl_p05": monte_carlo.get("terminal_pnl_p05"),
                    "mc_terminal_pnl_p50": monte_carlo.get("terminal_pnl_p50"),
                    "mc_terminal_pnl_p95": monte_carlo.get("terminal_pnl_p95"),
                    "mc_sharpe_like_p05": monte_carlo.get("sharpe_like_p05"),
                    "mc_max_drawdown_p95": monte_carlo.get("max_drawdown_p95"),
                    "source_path": metrics.get("source_path"),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute performance metrics for IMC result files or folders of logs.")
    parser.add_argument("path", type=Path, help="Result file or directory containing result files")
    parser.add_argument("--bootstrap-repetitions", type=int, default=1000, help="Monte Carlo repetitions; set to 0 to disable")
    parser.add_argument("--bootstrap-block-size", type=int, default=10, help="Block size for bootstrap resampling")
    parser.add_argument("--bootstrap-seed", type=int, default=0, help="Seed for bootstrap resampling")
    parser.add_argument("--json-out", type=Path, help="Optional path to write the metrics JSON")
    parser.add_argument("--csv-out", type=Path, help="Optional path to write a flattened CSV summary")
    args = parser.parse_args(argv)

    target_path = args.path.expanduser().resolve()
    files = discover_result_files(target_path)
    if not files:
        raise FileNotFoundError(f"No .json or .log result files found under {target_path}")

    metrics_list = [
        analyze_result_file(
            file_path,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_block_size=args.bootstrap_block_size,
            bootstrap_seed=args.bootstrap_seed,
        )
        for file_path in files
    ]

    if len(metrics_list) == 1:
        _print_single(metrics_list[0])
    else:
        _print_batch(metrics_list)

    if args.json_out:
        args.json_out.expanduser().resolve().write_text(json.dumps(metrics_list if len(metrics_list) > 1 else metrics_list[0], indent=2))
        print(f"Wrote metrics JSON to {args.json_out.expanduser().resolve()}")

    if args.csv_out:
        _write_csv(metrics_list, args.csv_out.expanduser().resolve())
        print(f"Wrote metrics CSV to {args.csv_out.expanduser().resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
