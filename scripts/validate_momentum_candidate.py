from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from itertools import product
from typing import Dict, Iterable

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.factors.momentum_variants import MOMENTUM_SPECS, compute_momentum_variant
from etf_rotation.storage import ParquetStore


DEFAULT_SPLITS = (
    ("2022", "2021-06-30", "2021-12-31", "2022-01-01", "2022-12-31"),
    ("2023", "2021-06-30", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2024", "2021-06-30", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2025", "2021-06-30", "2024-12-31", "2025-01-01", "2025-12-31"),
    ("2026H1", "2021-06-30", "2025-12-31", "2026-01-01", "2026-06-30"),
)


@dataclass(frozen=True)
class CandidateConfig:
    spec: str = "m_1_3_6"
    top_n: int = 3
    min_score: float | None = 0.60
    max_single_weight: float = 0.25
    transaction_cost_bps: float = 5.0
    rebalance_frequency: str = "W-FRI"
    min_avg_amount: float | None = None
    liquidity_window: int = 20


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the fixed momentum candidate with walk-forward and cost tests")
    parser.add_argument("--spec", default="m_1_3_6")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--min-score", default="0.60")
    parser.add_argument("--max-single-weight", type=float, default=0.25)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--cost-bps", default="0,5,10,20,50")
    parser.add_argument("--frequencies", default="W-FRI,M")
    parser.add_argument("--min-avg-amounts", default="none,50000000,100000000,200000000")
    parser.add_argument("--liquidity-window", type=int, default=20)
    parser.add_argument("--output-dir", default="data/processed/momentum_candidate_validation")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    candidate = CandidateConfig(
        spec=args.spec,
        top_n=args.top_n,
        min_score=parse_optional_float(args.min_score),
        max_single_weight=args.max_single_weight,
        transaction_cost_bps=args.transaction_cost_bps,
        liquidity_window=args.liquidity_window,
    )
    scores = compute_candidate_scores(daily, candidate.spec)

    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    walk_forward = run_walk_forward(daily, scores, cfg.benchmark_symbol, candidate, DEFAULT_SPLITS)
    walk_forward.to_parquet(out_dir / "walk_forward.parquet", index=False)
    walk_forward.to_csv(out_dir / "walk_forward.csv", index=False)

    cost_sensitivity = run_cost_sensitivity(daily, scores, cfg.benchmark_symbol, candidate, parse_cost_bps(args.cost_bps))
    cost_sensitivity.to_parquet(out_dir / "cost_sensitivity.parquet", index=False)
    cost_sensitivity.to_csv(out_dir / "cost_sensitivity.csv", index=False)

    implementation_sensitivity = run_implementation_sensitivity(
        daily,
        scores,
        cfg.benchmark_symbol,
        candidate,
        parse_strings(args.frequencies),
        parse_optional_floats(args.min_avg_amounts),
    )
    implementation_sensitivity.to_parquet(out_dir / "implementation_sensitivity.parquet", index=False)
    implementation_sensitivity.to_csv(out_dir / "implementation_sensitivity.csv", index=False)

    full_result = run_candidate(daily, scores, cfg.benchmark_symbol, candidate)
    full_result["curve"].to_parquet(out_dir / "candidate_full_curve.parquet", index=False)
    full_result["weights"].to_parquet(out_dir / "candidate_full_weights.parquet", index=False)

    summary = {
        "candidate": asdict(candidate),
        "benchmark_symbol": cfg.benchmark_symbol,
        "full_metrics": full_result["metrics"],
        "walk_forward": walk_forward.to_dict(orient="records"),
        "cost_sensitivity": cost_sensitivity.to_dict(orient="records"),
        "implementation_sensitivity": implementation_sensitivity.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


def compute_candidate_scores(daily: pd.DataFrame, spec: str) -> pd.DataFrame:
    if spec not in MOMENTUM_SPECS:
        raise ValueError(f"unknown momentum spec: {spec}")
    scores = compute_momentum_variant(daily, MOMENTUM_SPECS[spec])
    scores["baseline_score"] = scores["momentum_score"]
    return scores


def run_walk_forward(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    candidate: CandidateConfig,
    splits: Iterable[tuple[str, str, str, str, str]],
) -> pd.DataFrame:
    rows = []
    for label, train_start, train_end, test_start, test_end in splits:
        train_result = run_candidate(daily, scores, benchmark_symbol, candidate, start=train_start, end=train_end)
        test_result = run_candidate(daily, scores, benchmark_symbol, candidate, start=test_start, end=test_end)
        rows.append(
            {
                "split": label,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                **prefix_metrics("train", train_result["metrics"]),
                **prefix_metrics("test", test_result["metrics"]),
            }
        )
    return pd.DataFrame(rows)


def run_cost_sensitivity(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    candidate: CandidateConfig,
    cost_bps: Iterable[float],
) -> pd.DataFrame:
    rows = []
    for cost in cost_bps:
        tested = CandidateConfig(
            spec=candidate.spec,
            top_n=candidate.top_n,
            min_score=candidate.min_score,
            max_single_weight=candidate.max_single_weight,
            transaction_cost_bps=float(cost),
            rebalance_frequency=candidate.rebalance_frequency,
            min_avg_amount=candidate.min_avg_amount,
            liquidity_window=candidate.liquidity_window,
        )
        result = run_candidate(daily, scores, benchmark_symbol, tested)
        rows.append({"transaction_cost_bps": float(cost), **result["metrics"]})
    return pd.DataFrame(rows)


def run_implementation_sensitivity(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    candidate: CandidateConfig,
    frequencies: Iterable[str],
    min_avg_amounts: Iterable[float | None],
) -> pd.DataFrame:
    rows = []
    for frequency, min_avg_amount in product(frequencies, min_avg_amounts):
        tested = CandidateConfig(
            spec=candidate.spec,
            top_n=candidate.top_n,
            min_score=candidate.min_score,
            max_single_weight=candidate.max_single_weight,
            transaction_cost_bps=candidate.transaction_cost_bps,
            rebalance_frequency=frequency,
            min_avg_amount=min_avg_amount,
            liquidity_window=candidate.liquidity_window,
        )
        result = run_candidate(daily, scores, benchmark_symbol, tested)
        rows.append(
            {
                "rebalance_frequency": frequency,
                "min_avg_amount": min_avg_amount,
                "liquidity_window": candidate.liquidity_window,
                **result["metrics"],
            }
        )
    return pd.DataFrame(rows)


def run_candidate(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    candidate: CandidateConfig,
    start: str | None = None,
    end: str | None = None,
) -> Dict[str, object]:
    d = daily.copy()
    s = apply_liquidity_filter(scores, daily, candidate.min_avg_amount, candidate.liquidity_window)
    d["date"] = pd.to_datetime(d["date"])
    s["date"] = pd.to_datetime(s["date"])
    if start:
        start_ts = pd.Timestamp(start)
        d = d[d["date"] >= start_ts]
        s = s[s["date"] >= start_ts]
    if end:
        end_ts = pd.Timestamp(end)
        d = d[d["date"] <= end_ts]
        s = s[s["date"] <= end_ts]
    return run_weekly_rotation_backtest(
        daily=d,
        scores=s,
        benchmark_symbol=benchmark_symbol,
        config=BacktestConfig(
            top_n=candidate.top_n,
            min_score=candidate.min_score,
            max_single_weight=candidate.max_single_weight,
            transaction_cost_bps=candidate.transaction_cost_bps,
            rebalance_frequency=candidate.rebalance_frequency,
        ),
    )


def apply_liquidity_filter(
    scores: pd.DataFrame,
    daily: pd.DataFrame,
    min_avg_amount: float | None,
    window: int,
) -> pd.DataFrame:
    result = scores.copy()
    if min_avg_amount is None or min_avg_amount <= 0:
        return result
    liquidity = daily[["date", "symbol", "amount"]].copy()
    liquidity["date"] = pd.to_datetime(liquidity["date"])
    liquidity = liquidity.sort_values(["symbol", "date"])
    liquidity["avg_amount"] = (
        liquidity.groupby("symbol")["amount"]
        .rolling(window=window, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    result["date"] = pd.to_datetime(result["date"])
    result = result.merge(liquidity[["date", "symbol", "avg_amount"]], on=["date", "symbol"], how="left")
    result.loc[result["avg_amount"].fillna(0.0) < min_avg_amount, "baseline_score"] = -1.0
    return result


def parse_cost_bps(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_optional_floats(value: str) -> list[float | None]:
    return [parse_optional_float(item) for item in value.split(",") if item.strip()]


def parse_optional_float(value: str) -> float | None:
    stripped = value.strip().lower()
    if stripped in {"", "none", "null"}:
        return None
    return float(stripped)


def prefix_metrics(prefix: str, metrics: Dict[str, float]) -> Dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def sanitize_json(value):
    if isinstance(value, dict):
        return {key: sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


if __name__ == "__main__":
    main()
