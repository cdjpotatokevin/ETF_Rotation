from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.config import load_etf_pool, load_project_config, resolve_project_path
from etf_rotation.factors.common import cross_sectional_rank
from etf_rotation.ml import BASE_FEATURES, INTERACTION_FEATURES, build_ml_feature_frame, fit_logistic, fit_ridge, make_prediction_scores
from etf_rotation.storage import ParquetStore
from scripts.validate_momentum_candidate import DEFAULT_SPLITS, compute_candidate_scores, run_candidate


MODEL_SPECS = {
    "linear_momentum_rule": "当前线性动量规则",
    "ridge_return": "Ridge 预测21日收益",
    "logistic_top": "Logistic 预测前30%概率",
    "ridge_interaction": "Ridge 加交互项",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate conservative ML ETF rotation models with walk-forward validation")
    parser.add_argument("--output-dir", default="data/processed/ml_model_evaluation")
    parser.add_argument("--horizon", type=int, default=21)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.60)
    parser.add_argument("--max-single-weight", type=float, default=0.25)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    daily["date"] = pd.to_datetime(daily["date"])
    features = build_ml_feature_frame(daily, cfg.benchmark_symbol, horizon=args.horizon)
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    backtest_config = BacktestConfig(
        top_n=args.top_n,
        min_score=args.min_score,
        max_single_weight=args.max_single_weight,
        transaction_cost_bps=args.transaction_cost_bps,
    )

    walk_rows = []
    latest_rows = []
    all_latest_scores = []
    for model_key in MODEL_SPECS:
        for split in DEFAULT_SPLITS:
            label, train_start, train_end, test_start, test_end = split
            scores = scores_for_split(model_key, daily, features, train_start, train_end, test_start, test_end, cfg.benchmark_symbol)
            test_daily = filter_dates(daily, test_start, test_end)
            result = run_weekly_rotation_backtest(test_daily, scores, cfg.benchmark_symbol, backtest_config)
            walk_rows.append(
                {
                    "model": model_key,
                    "model_name": MODEL_SPECS[model_key],
                    "split": label,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    **result["metrics"],
                    "mean_rank_ic": mean_rank_ic(scores, features, test_start, test_end),
                }
            )

        latest_scores = latest_model_scores(model_key, daily, features, cfg.benchmark_symbol, args.horizon)
        all_latest_scores.append(latest_scores.assign(model=model_key, model_name=MODEL_SPECS[model_key]))
        latest_result = run_weekly_rotation_backtest(daily, latest_scores, cfg.benchmark_symbol, backtest_config)
        latest_rows.extend(latest_weight_rows(latest_result["weights"], model_key, MODEL_SPECS[model_key], daily))

    walk = pd.DataFrame(walk_rows)
    aggregate = aggregate_walk_forward(walk)
    latest = pd.DataFrame(latest_rows)
    latest_scores = pd.concat(all_latest_scores, ignore_index=True)

    walk.to_parquet(out_dir / "ml_walk_forward.parquet", index=False)
    walk.to_csv(out_dir / "ml_walk_forward.csv", index=False)
    aggregate.to_parquet(out_dir / "ml_model_summary.parquet", index=False)
    aggregate.to_csv(out_dir / "ml_model_summary.csv", index=False)
    latest.to_parquet(out_dir / "ml_latest_weights.parquet", index=False)
    latest.to_csv(out_dir / "ml_latest_weights.csv", index=False)
    latest_scores.to_parquet(out_dir / "ml_latest_scores.parquet", index=False)

    summary = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "horizon": args.horizon,
        "model_specs": MODEL_SPECS,
        "aggregate": aggregate.to_dict(orient="records"),
        "walk_forward": walk.to_dict(orient="records"),
        "latest_weights": latest.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


def scores_for_split(
    model_key: str,
    daily: pd.DataFrame,
    features: pd.DataFrame,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    benchmark_symbol: str,
) -> pd.DataFrame:
    if model_key == "linear_momentum_rule":
        scores = compute_candidate_scores(daily, "m_1_3_6")
        return filter_dates(scores, test_start, test_end)
    train = filter_dates(features, train_start, train_end)
    test = filter_dates(features, test_start, test_end)
    return predict_scores(model_key, train, test)


def latest_model_scores(model_key: str, daily: pd.DataFrame, features: pd.DataFrame, benchmark_symbol: str, horizon: int) -> pd.DataFrame:
    latest = pd.to_datetime(daily["date"]).max()
    if model_key == "linear_momentum_rule":
        return compute_candidate_scores(daily, "m_1_3_6")
    train_end = latest - pd.Timedelta(days=horizon + 5)
    train = features[(features["date"] <= train_end) & features["forward_return"].notna()].copy()
    test = features[features["date"] == latest].copy()
    return predict_scores(model_key, train, test)


def predict_scores(model_key: str, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    if test.empty:
        return pd.DataFrame(columns=["date", "symbol", "baseline_score", "prediction"])
    if model_key == "ridge_return":
        model = fit_ridge(train, BASE_FEATURES, alpha=10.0)
        predictions = test[["date", "symbol"]].copy()
        predictions["prediction"] = model.predict(test)
    elif model_key == "logistic_top":
        model = fit_logistic(train, BASE_FEATURES, alpha=2.0)
        predictions = test[["date", "symbol"]].copy()
        predictions["prediction"] = model.predict_proba(test)
    elif model_key == "ridge_interaction":
        columns = BASE_FEATURES + INTERACTION_FEATURES
        model = fit_ridge(train, columns, alpha=25.0)
        predictions = test[["date", "symbol"]].copy()
        predictions["prediction"] = model.predict(test)
    else:
        raise ValueError(f"unsupported model: {model_key}")
    return make_prediction_scores(predictions)


def filter_dates(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    return result[(result["date"] >= pd.Timestamp(start)) & (result["date"] <= pd.Timestamp(end))].copy()


def mean_rank_ic(scores: pd.DataFrame, features: pd.DataFrame, start: str, end: str) -> float:
    if scores.empty:
        return 0.0
    target = filter_dates(features, start, end)[["date", "symbol", "forward_return"]].dropna()
    merged = scores.merge(target, on=["date", "symbol"], how="inner")
    if merged.empty:
        return 0.0
    corr = merged.groupby("date").apply(spearman_without_scipy, include_groups=False)
    corr = corr.dropna()
    return float(corr.mean()) if not corr.empty else 0.0


def spearman_without_scipy(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return 0.0
    left = frame["baseline_score"].rank()
    right = frame["forward_return"].rank()
    value = left.corr(right)
    return float(value) if pd.notna(value) else 0.0


def aggregate_walk_forward(walk: pd.DataFrame) -> pd.DataFrame:
    grouped = walk.groupby(["model", "model_name"], as_index=False).agg(
        avg_test_return=("total_return", "mean"),
        avg_sharpe=("sharpe", "mean"),
        worst_drawdown=("max_drawdown", "min"),
        avg_excess_return=("excess_total_return", "mean"),
        avg_information_ratio=("information_ratio", "mean"),
        avg_rank_ic=("mean_rank_ic", "mean"),
        positive_periods=("total_return", lambda x: int((x > 0).sum())),
    )
    return grouped.sort_values(["avg_sharpe", "avg_test_return"], ascending=False)


def latest_weight_rows(weights: pd.DataFrame, model_key: str, model_name: str, daily: pd.DataFrame) -> list[dict]:
    if weights.empty:
        return []
    names = symbol_names(daily)
    frame = weights.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    latest = frame["date"].max()
    rows = []
    for _, row in frame[frame["date"] == latest].sort_values("weight", ascending=False).iterrows():
        symbol = row["symbol"]
        rows.append(
            {
                "model": model_key,
                "model_name": model_name,
                "date": latest.date().isoformat(),
                "symbol": symbol,
                "asset_name": "现金" if symbol == "CASH" else names.get(symbol, ""),
                "weight": float(row["weight"]),
            }
        )
    return rows


def symbol_names(daily: pd.DataFrame) -> dict[str, str]:
    assets = {asset.symbol: asset.name for asset in load_etf_pool()}
    if "name" not in daily:
        return assets
    data_names = daily.dropna(subset=["symbol"]).drop_duplicates("symbol").set_index("symbol")["name"].to_dict()
    return {**assets, **data_names}


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
