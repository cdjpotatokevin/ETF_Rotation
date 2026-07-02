from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from itertools import product
from typing import Dict, Iterable

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, build_weekly_weights, run_weighted_backtest
from etf_rotation.backtest.macro_overlay import MacroOverlayConfig, compute_macro_overlay, apply_macro_overlay
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate low-frequency macro risk/position overlay")
    parser.add_argument("--macro-path", default="data/raw/macro_indicators.parquet")
    parser.add_argument("--output-dir", default="data/processed/macro_overlay")
    parser.add_argument("--medium-thresholds", default="0.35,0.50,0.75")
    parser.add_argument("--high-thresholds", default="0.75,0.85,1.00,1.25,1.50")
    parser.add_argument("--medium-exposures", default="0.90,0.75")
    parser.add_argument("--high-exposures", default="0.75,0.50")
    parser.add_argument("--release-lag-days", type=int, default=10)
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    macro = pd.read_parquet(resolve_project_path(args.macro_path))
    scores = compute_candidate_scores(daily)
    backtest_config = BacktestConfig(top_n=3, min_score=0.60, max_single_weight=0.25, transaction_cost_bps=5.0)
    base_weights = build_weekly_weights(scores, backtest_config)
    base_result = run_weighted_backtest(daily, base_weights, cfg.benchmark_symbol, backtest_config.transaction_cost_bps)
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    curves: Dict[str, pd.DataFrame] = {}
    weights_by_key: Dict[str, pd.DataFrame] = {}
    overlays: Dict[str, pd.DataFrame] = {}
    for medium_threshold, high_threshold, medium_exposure, high_exposure in product(
        parse_floats(args.medium_thresholds),
        parse_floats(args.high_thresholds),
        parse_floats(args.medium_exposures),
        parse_floats(args.high_exposures),
    ):
        if high_threshold <= medium_threshold:
            continue
        config = MacroOverlayConfig(
            medium_risk_threshold=medium_threshold,
            high_risk_threshold=high_threshold,
            medium_risk_exposure=medium_exposure,
            high_risk_exposure=high_exposure,
            release_lag_days=args.release_lag_days,
        )
        key = make_key(config)
        overlay = compute_macro_overlay(macro, pd.to_datetime(daily["date"]), config)
        adjusted_weights = apply_macro_overlay(base_weights, overlay)
        full = run_weighted_backtest(daily, adjusted_weights, cfg.benchmark_symbol, backtest_config.transaction_cost_bps)
        walk_forward = run_walk_forward(daily, base_weights, macro, cfg.benchmark_symbol, backtest_config.transaction_cost_bps, config)
        row = {
            "key": key,
            **asdict(config),
            **prefix_metrics("full", full["metrics"]),
            "avg_target_exposure": float(overlay["target_exposure"].mean()),
            "high_risk_days": int((overlay["target_exposure"] == config.high_risk_exposure).sum()),
            "medium_risk_days": int((overlay["target_exposure"] == config.medium_risk_exposure).sum()),
            "objective": objective(base_result["metrics"], full["metrics"], walk_forward),
        }
        rows.append(row)
        curves[key] = full["curve"]
        weights_by_key[key] = adjusted_weights
        overlays[key] = overlay
        walk_forward.to_parquet(out_dir / f"walk_forward_{key}.parquet", index=False)

    result = pd.DataFrame(rows).sort_values("objective", ascending=False)
    result.to_parquet(out_dir / "macro_overlay_grid.parquet", index=False)
    result.to_csv(out_dir / "macro_overlay_grid.csv", index=False)
    base_result["curve"].to_parquet(out_dir / "base_candidate_curve.parquet", index=False)
    base_weights.to_parquet(out_dir / "base_candidate_weights.parquet", index=False)

    if result.empty:
        raise RuntimeError("no macro overlay candidates were evaluated")
    best = result.iloc[0].to_dict()
    best_key = str(best["key"])
    curves[best_key].to_parquet(out_dir / "best_macro_overlay_curve.parquet", index=False)
    weights_by_key[best_key].to_parquet(out_dir / "best_macro_overlay_weights.parquet", index=False)
    overlays[best_key].to_parquet(out_dir / "best_macro_overlay_signal.parquet", index=False)
    summary = {
        "base_metrics": base_result["metrics"],
        "best_key": best_key,
        "best_metrics": best,
        "best_walk_forward": pd.read_parquet(out_dir / f"walk_forward_{best_key}.parquet").to_dict(orient="records"),
    }
    (out_dir / "macro_overlay_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def compute_candidate_scores(daily: pd.DataFrame) -> pd.DataFrame:
    scores = compute_momentum_variant(daily, MOMENTUM_SPECS["m_1_3_6"])
    scores["baseline_score"] = scores["momentum_score"]
    return scores


def run_walk_forward(
    daily: pd.DataFrame,
    base_weights: pd.DataFrame,
    macro: pd.DataFrame,
    benchmark_symbol: str,
    transaction_cost_bps: float,
    config: MacroOverlayConfig,
) -> pd.DataFrame:
    rows = []
    for label, train_start, train_end, test_start, test_end in DEFAULT_SPLITS:
        train = run_period(daily, base_weights, macro, benchmark_symbol, transaction_cost_bps, config, train_start, train_end)
        test = run_period(daily, base_weights, macro, benchmark_symbol, transaction_cost_bps, config, test_start, test_end)
        rows.append(
            {
                "split": label,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                **prefix_metrics("train", train["metrics"]),
                **prefix_metrics("test", test["metrics"]),
            }
        )
    return pd.DataFrame(rows)


def run_period(
    daily: pd.DataFrame,
    base_weights: pd.DataFrame,
    macro: pd.DataFrame,
    benchmark_symbol: str,
    transaction_cost_bps: float,
    config: MacroOverlayConfig,
    start: str,
    end: str,
) -> Dict[str, object]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d[(d["date"] >= start_ts) & (d["date"] <= end_ts)]
    w = base_weights.copy()
    w["date"] = pd.to_datetime(w["date"])
    w = w[(w["date"] >= start_ts) & (w["date"] <= end_ts)]
    overlay = compute_macro_overlay(macro, d["date"], config)
    adjusted = apply_macro_overlay(w, overlay)
    return run_weighted_backtest(d, adjusted, benchmark_symbol, transaction_cost_bps)


def objective(base: Dict[str, float], tested: Dict[str, float], walk_forward: pd.DataFrame) -> float:
    drawdown_improvement = tested["max_drawdown"] - base["max_drawdown"]
    return (
        0.35 * tested["sharpe"]
        + 0.25 * tested["information_ratio"]
        + 0.20 * drawdown_improvement
        + 0.10 * tested["excess_total_return"]
        + 0.10 * float((walk_forward["test_max_drawdown"] > -0.16).mean())
    )


def parse_floats(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def prefix_metrics(prefix: str, metrics: Dict[str, float]) -> Dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def make_key(config: MacroOverlayConfig) -> str:
    return (
        f"med{fmt(config.medium_risk_threshold)}_high{fmt(config.high_risk_threshold)}"
        f"_me{fmt(config.medium_risk_exposure)}_he{fmt(config.high_risk_exposure)}_lag{config.release_lag_days}"
    )


def fmt(value: float) -> str:
    return str(value).replace(".", "p")


if __name__ == "__main__":
    main()
