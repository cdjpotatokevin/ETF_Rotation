from __future__ import annotations

import argparse
import json
import math
from itertools import product
from pathlib import Path
from typing import Dict

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.backtest.risk_control import RiskControlConfig, run_risk_controlled_backtest
from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.momentum_variants import MOMENTUM_SPECS, compute_momentum_variant
from etf_rotation.storage import ParquetStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune momentum variants and simple risk controls")
    parser.add_argument("--train-end", default="2024-12-31")
    parser.add_argument("--test-start", default="2025-01-01")
    parser.add_argument("--output-dir", default="data/processed/momentum_risk_tuning")
    parser.add_argument("--specs", default=",".join(MOMENTUM_SPECS.keys()))
    parser.add_argument("--top-n", default="3,5")
    parser.add_argument("--min-scores", default="none,0.55,0.60")
    parser.add_argument("--target-vols", default="none,0.18,0.22")
    parser.add_argument("--stop-losses", default="none,0.12,0.18")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    rows = []
    curves: Dict[str, pd.DataFrame] = {}

    for spec_name, top_n, min_score, target_vol, stop_loss in product(
        parse_specs(args.specs),
        parse_ints(args.top_n),
        parse_optional_floats(args.min_scores),
        parse_optional_floats(args.target_vols),
        parse_optional_floats(args.stop_losses),
    ):
        key = make_key(spec_name, top_n, min_score, target_vol, stop_loss)
        scores = compute_momentum_scores(daily, spec_name)
        backtest_config = BacktestConfig(top_n=top_n, max_single_weight=0.25, min_score=min_score)
        risk_config = RiskControlConfig(portfolio_stop_loss=stop_loss, target_vol=target_vol)
        train = run_period(daily, scores, cfg.benchmark_symbol, backtest_config, risk_config, end=args.train_end)
        test = run_period(daily, scores, cfg.benchmark_symbol, backtest_config, risk_config, start=args.test_start)
        full = run_period(daily, scores, cfg.benchmark_symbol, backtest_config, risk_config)
        ic = calculate_factor_ic(daily, scores)
        baseline_ic = float(ic.loc[ic["factor"] == "baseline_score", "mean_ic"].iloc[0])
        row = {
            "key": key,
            "spec": spec_name,
            "top_n": top_n,
            "min_score": min_score,
            "target_vol": target_vol,
            "stop_loss": stop_loss,
            **prefix_metrics("train", train["metrics"]),
            **prefix_metrics("test", test["metrics"]),
            **prefix_metrics("full", full["metrics"]),
            "full_baseline_mean_ic": baseline_ic,
            "objective": objective(train["metrics"], test["metrics"]),
        }
        rows.append(row)
        curves[key] = full["curve"]

    result = pd.DataFrame(rows).sort_values("objective", ascending=False)
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_dir / "momentum_risk_grid.parquet", index=False)
    result.to_csv(out_dir / "momentum_risk_grid.csv", index=False)
    best = result.iloc[0].to_dict()
    best_key = str(best["key"])
    curves[best_key].to_parquet(out_dir / "best_momentum_risk_curve.parquet", index=False)
    payload = sanitize_json({"best_key": best_key, "metrics": best, "train_end": args.train_end, "test_start": args.test_start})
    (out_dir / "best_momentum_risk.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"best_key": best_key, "metrics": sanitize_json(best)}, ensure_ascii=False, indent=2))


def compute_momentum_scores(daily: pd.DataFrame, spec_name: str) -> pd.DataFrame:
    scores = compute_momentum_variant(daily, MOMENTUM_SPECS[spec_name])
    scores["baseline_score"] = scores["momentum_score"]
    return scores


def run_period(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    backtest_config: BacktestConfig,
    risk_config: RiskControlConfig,
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
    if risk_config.portfolio_stop_loss or risk_config.target_vol:
        return run_risk_controlled_backtest(d, s, benchmark_symbol, backtest_config, risk_config)
    return run_weekly_rotation_backtest(d, s, benchmark_symbol, backtest_config)


def prefix_metrics(prefix: str, metrics: Dict[str, float]) -> Dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def objective(train: Dict[str, float], test: Dict[str, float]) -> float:
    return (
        0.25 * train["sharpe"]
        + 0.35 * test["sharpe"]
        + 0.15 * train["information_ratio"]
        + 0.15 * test["information_ratio"]
        + 0.10 * test["excess_total_return"]
        + min(0.0, train["max_drawdown"]) * 0.10
        + min(0.0, test["max_drawdown"]) * 0.15
    )


def make_key(spec: str, top_n: int, min_score: float | None, target_vol: float | None, stop_loss: float | None) -> str:
    return f"{spec}_top{top_n}_min{fmt(min_score)}_vol{fmt(target_vol)}_stop{fmt(stop_loss)}"


def fmt(value: float | None) -> str:
    return "none" if value is None else str(value).replace(".", "p")


def sanitize_json(value):
    if isinstance(value, dict):
        return {key: sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def parse_specs(value: str) -> list[str]:
    specs = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in specs if item not in MOMENTUM_SPECS]
    if unknown:
        raise ValueError(f"unknown momentum specs: {unknown}")
    return specs


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_optional_floats(value: str) -> list[float | None]:
    rows = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        rows.append(None if item.lower() == "none" else float(item))
    return rows


if __name__ == "__main__":
    main()
