from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.config import load_etf_pool, load_project_config, resolve_project_path
from etf_rotation.data.window import filter_daily_window
from etf_rotation.storage import ParquetStore
from scripts.validate_momentum_candidate import (
    CandidateConfig,
    DEFAULT_SPLITS,
    compute_candidate_scores,
    prefix_metrics,
    run_candidate,
    run_walk_forward,
)


@dataclass(frozen=True)
class AllocationVariant:
    key: str
    name: str
    top_n: int
    max_single_weight: float
    min_score: float | None = 0.60
    spec: str = "m_1_3_6"
    transaction_cost_bps: float = 5.0


DEFAULT_VARIANTS = (
    AllocationVariant(
        key="top3_cap25_cash",
        name="Top3 单只25%上限，剩余现金",
        top_n=3,
        max_single_weight=0.25,
    ),
    AllocationVariant(
        key="top3_full_cap33",
        name="Top3 满仓集中，单只33.33%",
        top_n=3,
        max_single_weight=1.0 / 3.0,
    ),
    AllocationVariant(
        key="top4_full_cap25",
        name="Top4 满仓分散，单只25%",
        top_n=4,
        max_single_weight=0.25,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare portfolio allocation variants for the momentum candidate")
    parser.add_argument("--output-dir", default="data/processed/allocation_variant_comparison")
    args = parser.parse_args()

    cfg = load_project_config()
    daily = filter_daily_window(ParquetStore(cfg.raw_dir).read("etf_daily"), cfg.data_start, cfg.data_end)
    scores = compute_candidate_scores(daily, "m_1_3_6")
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    full_rows = []
    latest_rows = []
    walk_rows = []
    curves: Dict[str, pd.DataFrame] = {}
    weights_by_variant: Dict[str, pd.DataFrame] = {}

    for variant in DEFAULT_VARIANTS:
        candidate = to_candidate_config(variant)
        result = run_candidate(daily, scores, cfg.benchmark_symbol, candidate)
        weights = result["weights"].copy()
        curve = result["curve"].copy()
        weights_by_variant[variant.key] = weights
        curves[variant.key] = curve

        full_rows.append(
            {
                **variant_metadata(variant),
                **result["metrics"],
                "latest_rebalance_date": latest_date(weights),
                "latest_equity_exposure": latest_equity_exposure(weights),
            }
        )
        latest_rows.extend(latest_weight_rows(weights, variant, daily))

        walk_forward = run_walk_forward(daily, scores, cfg.benchmark_symbol, candidate, DEFAULT_SPLITS)
        for record in walk_forward.to_dict(orient="records"):
            walk_rows.append({**variant_metadata(variant), **record})

    full = pd.DataFrame(full_rows).sort_values(["sharpe", "total_return"], ascending=False)
    latest = pd.DataFrame(latest_rows).sort_values(["key", "weight"], ascending=[True, False])
    walk = pd.DataFrame(walk_rows).sort_values(["key", "split"])

    full.to_parquet(out_dir / "allocation_variant_metrics.parquet", index=False)
    full.to_csv(out_dir / "allocation_variant_metrics.csv", index=False)
    latest.to_parquet(out_dir / "latest_allocation_weights.parquet", index=False)
    latest.to_csv(out_dir / "latest_allocation_weights.csv", index=False)
    walk.to_parquet(out_dir / "allocation_variant_walk_forward.parquet", index=False)
    walk.to_csv(out_dir / "allocation_variant_walk_forward.csv", index=False)
    for key, curve in curves.items():
        curve.to_parquet(out_dir / f"{key}_curve.parquet", index=False)
    for key, weights in weights_by_variant.items():
        weights.to_parquet(out_dir / f"{key}_weights.parquet", index=False)

    summary = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "variants": [variant_metadata(item) for item in DEFAULT_VARIANTS],
        "full_metrics": full.to_dict(orient="records"),
        "latest_weights": latest.to_dict(orient="records"),
        "walk_forward": walk.to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary), ensure_ascii=False, indent=2))


def to_candidate_config(variant: AllocationVariant) -> CandidateConfig:
    return CandidateConfig(
        spec=variant.spec,
        top_n=variant.top_n,
        min_score=variant.min_score,
        max_single_weight=variant.max_single_weight,
        transaction_cost_bps=variant.transaction_cost_bps,
    )


def variant_metadata(variant: AllocationVariant) -> dict:
    return {
        "key": variant.key,
        "variant_name": variant.name,
        "top_n": variant.top_n,
        "max_single_weight": variant.max_single_weight,
        "min_score": variant.min_score,
        "spec": variant.spec,
        "transaction_cost_bps": variant.transaction_cost_bps,
    }


def latest_date(weights: pd.DataFrame) -> str | None:
    if weights.empty:
        return None
    return pd.to_datetime(weights["date"]).max().date().isoformat()


def latest_equity_exposure(weights: pd.DataFrame) -> float:
    if weights.empty:
        return 0.0
    frame = weights.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    latest = frame["date"].max()
    latest_weights = frame[(frame["date"] == latest) & (frame["symbol"] != "CASH")]
    return float(latest_weights["weight"].sum())


def latest_weight_rows(weights: pd.DataFrame, variant: AllocationVariant, daily: pd.DataFrame) -> list[dict]:
    if weights.empty:
        return []
    frame = weights.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    latest = frame["date"].max()
    latest_weights = frame[frame["date"] == latest].copy()
    names = symbol_names(daily)
    rows = []
    for _, row in latest_weights.iterrows():
        symbol = row["symbol"]
        rows.append(
            {
                **variant_metadata(variant),
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
