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
    build_ml_regime_weights,
    build_regime_decision_frame,
    fit_regime_model,
    predict_regime_probabilities,
    run_ml_regime_overlay_backtest,
    static_allocation_result,
)
from etf_rotation.storage import ParquetStore
from scripts.evaluate_expanded_pool import merge_existing_and_new_daily
from scripts.evaluate_ml_regime_overlay import aggregate_thresholds, filter_dates, prefix_metrics
from scripts.validate_momentum_candidate import DEFAULT_SPLITS, compute_candidate_scores


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML regime overlay on the expanded A-share ETF pool")
    parser.add_argument("--output-dir", default="data/processed/expanded_a_share_ml_regime_overlay")
    parser.add_argument("--new-data-name", default="expanded_a_share_new_etf_daily")
    parser.add_argument("--thresholds", default="0.50,0.55,0.60,0.65")
    args = parser.parse_args()

    cfg = load_project_config()
    raw_store = ParquetStore(cfg.raw_dir)
    base_daily = raw_store.read("etf_daily")
    new_daily = raw_store.read(args.new_data_name)
    daily = merge_existing_and_new_daily(base_daily, new_daily)
    thresholds = [float(item) for item in args.thresholds.split(",") if item.strip()]
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = evaluate_ml_overlay_for_pool(daily, cfg.benchmark_symbol, thresholds, out_dir)
    summary = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "thresholds": thresholds,
        "best_threshold": result["best_threshold"],
        "aggregate": result["aggregate"].to_dict(orient="records"),
        "walk_forward": result["walk_forward"].to_dict(orient="records"),
        "latest_probability": result["latest_probability"].to_dict(orient="records"),
        "latest_weights": result["latest_weights"].to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


def evaluate_ml_overlay_for_pool(
    daily: pd.DataFrame,
    benchmark_symbol: str,
    thresholds: list[float],
    out_dir: Path,
) -> dict:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    scores = compute_candidate_scores(daily, "m_1_3_6")
    decision_frame = build_regime_decision_frame(daily, scores, benchmark_symbol)

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
            ml_result = run_ml_regime_overlay_backtest(period_daily, period_scores, probabilities, benchmark_symbol, config)
            defensive = static_allocation_result(period_daily, period_scores, benchmark_symbol, 3, 0.60, 0.25, 5.0)
            full = static_allocation_result(period_daily, period_scores, benchmark_symbol, 3, 0.60, 1.0 / 3.0, 5.0)
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
    latest = latest_signal(daily, scores, decision_frame, benchmark_symbol, best_threshold)
    latest_weights = add_asset_names(latest["weights"], daily)

    decision_frame.to_parquet(out_dir / "expanded_regime_decision_frame.parquet", index=False)
    walk.to_parquet(out_dir / "expanded_ml_regime_walk_forward.parquet", index=False)
    walk.to_csv(out_dir / "expanded_ml_regime_walk_forward.csv", index=False)
    aggregate.to_parquet(out_dir / "expanded_ml_regime_summary.parquet", index=False)
    aggregate.to_csv(out_dir / "expanded_ml_regime_summary.csv", index=False)
    latest_weights.to_parquet(out_dir / "latest_expanded_ml_regime_weights.parquet", index=False)
    latest["probabilities"].to_parquet(out_dir / "latest_expanded_ml_regime_probability.parquet", index=False)
    return {
        "best_threshold": best_threshold,
        "aggregate": aggregate,
        "walk_forward": walk,
        "latest_probability": latest["probabilities"],
        "latest_weights": latest_weights,
    }


def latest_signal(daily: pd.DataFrame, scores: pd.DataFrame, decision_frame: pd.DataFrame, benchmark_symbol: str, threshold: float) -> dict:
    latest_date = pd.to_datetime(daily["date"]).max()
    train = decision_frame[(decision_frame["date"] < latest_date) & decision_frame["target_full"].notna()].copy()
    test = decision_frame[decision_frame["date"] == latest_date].copy()
    model = fit_regime_model(train)
    probabilities = predict_regime_probabilities(model, test)
    config = MLRegimeOverlayConfig(probability_threshold=threshold)
    weights = build_ml_regime_weights(scores, probabilities, config)
    weights["date"] = pd.to_datetime(weights["date"])
    return {
        "probabilities": probabilities,
        "weights": weights[weights["date"] == weights["date"].max()].copy(),
    }


def add_asset_names(weights: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    result = weights.copy()
    names = daily.dropna(subset=["symbol"]).drop_duplicates("symbol").set_index("symbol")["name"].to_dict()
    result["asset_name"] = result["symbol"].map(lambda symbol: "现金" if symbol == "CASH" else names.get(symbol, ""))
    return result


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
