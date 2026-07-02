from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest
from etf_rotation.config import load_project_config
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.scoring import compute_baseline_scores
from etf_rotation.storage import ParquetStore


def run_baseline_backtest() -> Dict[str, Path | Dict[str, float]]:
    cfg = load_project_config()
    raw_store = ParquetStore(cfg.raw_dir)
    factor_store = ParquetStore(cfg.factor_dir)
    processed_store = ParquetStore(cfg.processed_dir)

    daily = raw_store.read("etf_daily")
    scores = compute_baseline_scores(daily)
    score_path = factor_store.write("baseline_scores", scores)
    ic = calculate_factor_ic(daily, scores)
    ic_path = factor_store.write("baseline_factor_ic", ic)

    result = run_weekly_rotation_backtest(
        daily=daily,
        scores=scores,
        benchmark_symbol=cfg.benchmark_symbol,
        config=BacktestConfig(rebalance_frequency=cfg.rebalance_frequency),
    )
    curve = result["curve"]
    weights = result["weights"]
    metrics = result["metrics"]
    curve_path = processed_store.write("baseline_backtest_curve", curve)
    weights_path = processed_store.write("baseline_backtest_weights", weights)
    metrics_path = processed_store.base_dir / "baseline_backtest_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "score_path": score_path,
        "ic_path": ic_path,
        "curve_path": curve_path,
        "weights_path": weights_path,
        "metrics_path": metrics_path,
        "metrics": metrics,
    }
