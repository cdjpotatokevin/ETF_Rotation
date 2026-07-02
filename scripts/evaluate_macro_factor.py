from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.macro import compute_macro_resonance
from etf_rotation.factors.scoring import BASELINE_WEIGHTS, compute_baseline_scores
from etf_rotation.storage import ParquetStore


MACRO_BLEND_WEIGHTS = {
    "momentum_score": 0.45,
    "fund_flow_score": 0.20,
    "crowding_score": 0.20,
    "macro_resonance_score": 0.15,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate macro-resonance factor on real ETF data")
    parser.add_argument("--macro-path", default="data/raw/macro_indicators.parquet")
    parser.add_argument("--output-dir", default="data/processed/macro_factor")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--min-score", default="none")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = ParquetStore(cfg.raw_dir).read("etf_daily")
    macro = pd.read_parquet(resolve_project_path(args.macro_path))
    baseline = compute_baseline_scores(daily)
    macro_scores = compute_macro_resonance(daily, macro)
    baseline["date"] = pd.to_datetime(baseline["date"])
    macro_scores["date"] = pd.to_datetime(macro_scores["date"])
    scores = baseline.merge(macro_scores, on=["date", "symbol"], how="left")
    scores["macro_resonance_score"] = scores["macro_resonance_score"].fillna(0.5)
    scores["baseline_with_macro_score"] = apply_weights(scores, MACRO_BLEND_WEIGHTS)
    scores["baseline_score"] = scores["baseline_with_macro_score"]

    ic = calculate_factor_ic(daily, scores)
    result = run_weekly_rotation_backtest(
        daily,
        scores,
        cfg.benchmark_symbol,
        BacktestConfig(top_n=args.top_n, min_score=parse_optional_float(args.min_score)),
    )

    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out_dir / "macro_scores.parquet", index=False)
    ic.to_parquet(out_dir / "macro_factor_ic.parquet", index=False)
    result["curve"].to_parquet(out_dir / "macro_backtest_curve.parquet", index=False)
    result["weights"].to_parquet(out_dir / "macro_backtest_weights.parquet", index=False)
    metrics = {
        "weights": MACRO_BLEND_WEIGHTS,
        "legacy_baseline_weights": BASELINE_WEIGHTS,
        "backtest": result["metrics"],
        "ic": ic.to_dict(orient="records"),
    }
    (out_dir / "macro_factor_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def apply_weights(scores: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
    return sum(scores[column].fillna(0.5) * weight for column, weight in weights.items())


def parse_optional_float(value: str) -> float | None:
    stripped = value.strip().lower()
    return None if stripped in {"none", "null", ""} else float(stripped)


if __name__ == "__main__":
    main()
