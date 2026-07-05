from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.ml_overlay import (
    MLRegimeOverlayConfig,
    build_regime_decision_frame,
    fit_regime_model,
    predict_regime_probabilities,
    run_ml_regime_overlay_backtest,
    static_allocation_result,
)
from etf_rotation.storage import ParquetStore
from scripts.validate_momentum_candidate import DEFAULT_SPLITS, compute_candidate_scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML regime overlay for choosing defensive vs full Top3 exposure")
    parser.add_argument("--output-dir", default="data/processed/ml_regime_overlay")
    parser.add_argument("--thresholds", default="0.50,0.55,0.60,0.65")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    daily["date"] = pd.to_datetime(daily["date"])
    scores = compute_candidate_scores(daily, "m_1_3_6")
    decision_frame = build_regime_decision_frame(daily, scores, cfg.benchmark_symbol)
    thresholds = [float(item) for item in args.thresholds.split(",") if item.strip()]
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    walk_rows = []
    for threshold in thresholds:
        for label, train_start, train_end, test_start, test_end in DEFAULT_SPLITS:
            train = filter_dates(decision_frame, train_start, train_end).dropna(subset=["target_full"])
            test = filter_dates(decision_frame, test_start, test_end)
            if train.empty or test.empty:
                continue
            model = fit_regime_model(train)
            probabilities = predict_regime_probabilities(model, test)
            period_daily = filter_dates(daily, test_start, test_end)
            period_scores = filter_dates(scores, test_start, test_end)
            config = MLRegimeOverlayConfig(probability_threshold=threshold)
            ml_result = run_ml_regime_overlay_backtest(period_daily, period_scores, probabilities, cfg.benchmark_symbol, config)
            defensive = static_allocation_result(period_daily, period_scores, cfg.benchmark_symbol, 3, 0.60, 0.25, 5.0)
            full = static_allocation_result(period_daily, period_scores, cfg.benchmark_symbol, 3, 0.60, 1.0 / 3.0, 5.0)
            walk_rows.append(
                {
                    "threshold": threshold,
                    "split": label,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "avg_prob_full": float(probabilities["prob_full"].mean()),
                    "full_signal_ratio": float((probabilities["prob_full"] >= threshold).mean()),
                    **prefix_metrics("ml", ml_result["metrics"]),
                    **prefix_metrics("defensive", defensive["metrics"]),
                    **prefix_metrics("full", full["metrics"]),
                }
            )

    walk = pd.DataFrame(walk_rows)
    aggregate = aggregate_thresholds(walk)
    best_threshold = float(aggregate.iloc[0]["threshold"]) if not aggregate.empty else thresholds[0]
    latest = latest_signal(daily, scores, decision_frame, cfg.benchmark_symbol, best_threshold)

    decision_frame.to_parquet(out_dir / "regime_decision_frame.parquet", index=False)
    walk.to_parquet(out_dir / "ml_regime_walk_forward.parquet", index=False)
    walk.to_csv(out_dir / "ml_regime_walk_forward.csv", index=False)
    aggregate.to_parquet(out_dir / "ml_regime_summary.parquet", index=False)
    aggregate.to_csv(out_dir / "ml_regime_summary.csv", index=False)
    latest["weights"].to_parquet(out_dir / "latest_ml_regime_weights.parquet", index=False)
    latest["probabilities"].to_parquet(out_dir / "latest_ml_regime_probability.parquet", index=False)

    summary = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "thresholds": thresholds,
        "best_threshold": best_threshold,
        "aggregate": aggregate.to_dict(orient="records"),
        "walk_forward": walk.to_dict(orient="records"),
        "latest_probability": latest["probabilities"].to_dict(orient="records"),
        "latest_weights": latest["weights"].to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


def latest_signal(daily: pd.DataFrame, scores: pd.DataFrame, decision_frame: pd.DataFrame, benchmark_symbol: str, threshold: float) -> dict:
    latest_date = pd.to_datetime(daily["date"]).max()
    train = decision_frame[(decision_frame["date"] < latest_date) & decision_frame["target_full"].notna()].copy()
    test = decision_frame[decision_frame["date"] == latest_date].copy()
    model = fit_regime_model(train)
    probabilities = predict_regime_probabilities(model, test)
    config = MLRegimeOverlayConfig(probability_threshold=threshold)
    weights = run_ml_regime_overlay_backtest(daily, scores, probabilities, benchmark_symbol, config)["weights"]
    weights["date"] = pd.to_datetime(weights["date"])
    return {
        "probabilities": probabilities,
        "weights": weights[weights["date"] == weights["date"].max()].copy(),
    }


def aggregate_thresholds(walk: pd.DataFrame) -> pd.DataFrame:
    if walk.empty:
        return walk
    grouped = walk.groupby("threshold", as_index=False).agg(
        avg_ml_return=("ml_total_return", "mean"),
        avg_ml_sharpe=("ml_sharpe", "mean"),
        worst_ml_drawdown=("ml_max_drawdown", "min"),
        avg_ml_excess=("ml_excess_total_return", "mean"),
        avg_ml_ir=("ml_information_ratio", "mean"),
        avg_defensive_return=("defensive_total_return", "mean"),
        avg_defensive_sharpe=("defensive_sharpe", "mean"),
        worst_defensive_drawdown=("defensive_max_drawdown", "min"),
        avg_defensive_ir=("defensive_information_ratio", "mean"),
        avg_full_return=("full_total_return", "mean"),
        avg_full_sharpe=("full_sharpe", "mean"),
        worst_full_drawdown=("full_max_drawdown", "min"),
        avg_full_ir=("full_information_ratio", "mean"),
        avg_full_signal_ratio=("full_signal_ratio", "mean"),
        positive_periods=("ml_total_return", lambda x: int((x > 0).sum())),
    )
    grouped["objective"] = (
        grouped["avg_ml_sharpe"]
        + 0.35 * grouped["avg_ml_ir"]
        + 0.25 * grouped["avg_ml_return"]
        + grouped["worst_ml_drawdown"].clip(upper=0.0)
    )
    return grouped.sort_values(["objective", "avg_ml_sharpe"], ascending=False)


def filter_dates(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    return result[(result["date"] >= pd.Timestamp(start)) & (result["date"] <= pd.Timestamp(end))].copy()


def prefix_metrics(prefix: str, metrics: dict) -> dict:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def sanitize_json(value):
    if isinstance(value, dict):
        return {key: sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


if __name__ == "__main__":
    main()
