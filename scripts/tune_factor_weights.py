from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.scoring import compute_baseline_scores
from etf_rotation.storage import ParquetStore


FACTOR_COLUMNS = ["momentum_score", "fund_flow_score", "crowding_score"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune ETF rotation factor weights with a train/test split")
    parser.add_argument("--train-end", default="2024-12-31")
    parser.add_argument("--test-start", default="2025-01-01")
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--output-dir", default="data/processed/weight_tuning")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    scores = compute_baseline_scores(daily)
    grid = weight_grid(args.step)
    rows = []
    curves: Dict[str, pd.DataFrame] = {}
    weights_by_key: Dict[str, Dict[str, float]] = {}

    for weights in grid:
        key = key_for(weights)
        weighted = apply_weights(scores, weights)
        train_result = run_period(daily, weighted, cfg.benchmark_symbol, end=args.train_end)
        test_result = run_period(daily, weighted, cfg.benchmark_symbol, start=args.test_start)
        full_result = run_period(daily, weighted, cfg.benchmark_symbol)
        ic = calculate_factor_ic(daily, weighted)
        baseline_ic = float(ic.loc[ic["factor"] == "baseline_score", "mean_ic"].iloc[0])
        row = {
            "key": key,
            **{f"w_{name.replace('_score', '')}": value for name, value in weights.items()},
            **prefix_metrics("train", train_result["metrics"]),
            **prefix_metrics("test", test_result["metrics"]),
            **prefix_metrics("full", full_result["metrics"]),
            "full_baseline_mean_ic": baseline_ic,
            "objective": objective(train_result["metrics"], test_result["metrics"]),
        }
        rows.append(row)
        curves[key] = full_result["curve"]
        weights_by_key[key] = weights

    result = pd.DataFrame(rows).sort_values("objective", ascending=False)
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_dir / "factor_weight_grid.parquet", index=False)
    result.to_csv(out_dir / "factor_weight_grid.csv", index=False)

    best = result.iloc[0].to_dict()
    best_key = str(best["key"])
    curves[best_key].to_parquet(out_dir / "best_weight_backtest_curve.parquet", index=False)
    (out_dir / "best_weights.json").write_text(
        json.dumps(
            {
                "best_key": best_key,
                "weights": weights_by_key[best_key],
                "metrics": best,
                "train_end": args.train_end,
                "test_start": args.test_start,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"best_key": best_key, "weights": weights_by_key[best_key], "metrics": best}, ensure_ascii=False, indent=2))


def weight_grid(step: float) -> List[Dict[str, float]]:
    units = int(round(1 / step))
    rows = []
    for m, f in product(range(units + 1), repeat=2):
        c = units - m - f
        if c < 0:
            continue
        rows.append(
            {
                "momentum_score": round(m * step, 10),
                "fund_flow_score": round(f * step, 10),
                "crowding_score": round(c * step, 10),
            }
        )
    return rows


def apply_weights(scores: pd.DataFrame, weights: Dict[str, float]) -> pd.DataFrame:
    result = scores.copy()
    result["baseline_score"] = sum(result[col].fillna(0.5) * weight for col, weight in weights.items())
    return result


def run_period(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> Dict[str, object]:
    d = daily.copy()
    s = scores.copy()
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
        config=BacktestConfig(),
    )


def prefix_metrics(prefix: str, metrics: Dict[str, float]) -> Dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def objective(train: Dict[str, float], test: Dict[str, float]) -> float:
    # Prefer train/test robustness over one lucky full-sample result.
    return (
        0.35 * train["sharpe"]
        + 0.35 * test["sharpe"]
        + 0.20 * test["information_ratio"]
        + 0.10 * test["excess_total_return"]
        + min(0.0, test["max_drawdown"]) * 0.15
    )


def key_for(weights: Dict[str, float]) -> str:
    return "m{momentum_score:.1f}_f{fund_flow_score:.1f}_c{crowding_score:.1f}".format(**weights)


if __name__ == "__main__":
    main()
