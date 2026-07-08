from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.storage import ParquetStore
from scripts.compare_allocation_variants import DEFAULT_VARIANTS, latest_equity_exposure, to_candidate_config, variant_metadata
from scripts.evaluate_expanded_pool import latest_weight_rows, merge_existing_and_new_daily
from scripts.validate_momentum_candidate import compute_candidate_scores, run_candidate, run_walk_forward


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an independent long-sample ETF rotation backtest")
    parser.add_argument("--start-date", default="2019-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", default="data/processed/long_sample_2019")
    parser.add_argument("--new-data-name", default="expanded_a_share_new_etf_daily")
    parser.add_argument("--train-end-year", type=int, default=2020)
    args = parser.parse_args()

    cfg = load_project_config()
    end = args.end_date or cfg.data_end.isoformat()
    store = ParquetStore(cfg.raw_dir)
    base_daily = filter_dates(store.read("etf_daily"), args.start_date, end)
    new_daily = store.read(args.new_data_name) if store.exists(args.new_data_name) else pd.DataFrame(columns=base_daily.columns)
    expanded_daily = filter_dates(merge_existing_and_new_daily(base_daily, new_daily), args.start_date, end)
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    splits = build_long_sample_splits(args.start_date, end, train_end_year=args.train_end_year)
    summary = evaluate_pools(base_daily, expanded_daily, cfg.benchmark_symbol, splits, out_dir)
    payload = {
        "start_date": args.start_date,
        "end_date": end,
        "benchmark_symbol": cfg.benchmark_symbol,
        "splits": splits,
        "data_availability": {
            "base": data_availability(base_daily),
            "expanded": data_availability(expanded_daily),
        },
        "full_metrics": summary["full_metrics"].to_dict(orient="records"),
        "walk_forward": summary["walk_forward"].to_dict(orient="records"),
        "latest_weights": summary["latest_weights"].to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(payload), ensure_ascii=False, indent=2))


def build_long_sample_splits(start_date: str, end_date: str, *, train_end_year: int = 2020) -> list[tuple[str, str, str, str, str]]:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    splits = []
    for year in range(train_end_year + 1, end.year + 1):
        test_start = pd.Timestamp(date(year, 1, 1))
        test_end = min(pd.Timestamp(date(year, 12, 31)), end)
        if test_start > end:
            break
        label = f"{year}YTD" if year == end.year and test_end < pd.Timestamp(date(year, 12, 31)) else str(year)
        splits.append(
            (
                label,
                start.date().isoformat(),
                date(year - 1, 12, 31).isoformat(),
                test_start.date().isoformat(),
                test_end.date().isoformat(),
            )
        )
    return splits


def evaluate_pools(
    base_daily: pd.DataFrame,
    expanded_daily: pd.DataFrame,
    benchmark_symbol: str,
    splits: list[tuple[str, str, str, str, str]],
    out_dir: Path,
) -> dict[str, pd.DataFrame]:
    rows = []
    walk_rows = []
    latest_rows = []
    pools = [
        ("base_pool", "原19只ETF池", base_daily),
        ("expanded_pool", "扩展A股ETF池", expanded_daily),
    ]
    for pool_key, pool_name, daily in pools:
        scores = compute_candidate_scores(daily, "m_1_3_6")
        available_splits = filter_splits_with_data(daily, splits)
        for variant in DEFAULT_VARIANTS:
            candidate = to_candidate_config(variant)
            result = run_candidate(daily, scores, benchmark_symbol, candidate)
            weights = result["weights"].copy()
            curve = result["curve"].copy()
            rows.append(
                {
                    "pool_key": pool_key,
                    "pool_name": pool_name,
                    **variant_metadata(variant),
                    **result["metrics"],
                    "latest_equity_exposure": latest_equity_exposure(weights),
                }
            )
            latest_rows.extend(latest_weight_rows(weights, daily, pool_key, pool_name, variant.key, variant.name))
            curve.to_parquet(out_dir / f"{pool_key}_{variant.key}_curve.parquet", index=False)
            weights.to_parquet(out_dir / f"{pool_key}_{variant.key}_weights.parquet", index=False)
            walk = run_walk_forward(daily, scores, benchmark_symbol, candidate, available_splits)
            for record in walk.to_dict(orient="records"):
                walk_rows.append({"pool_key": pool_key, "pool_name": pool_name, **variant_metadata(variant), **record})

    full_metrics = pd.DataFrame(rows).sort_values(["key", "pool_key"])
    walk_forward = pd.DataFrame(walk_rows).sort_values(["key", "pool_key", "split"])
    latest_weights = pd.DataFrame(latest_rows).sort_values(["pool_key", "key", "weight"], ascending=[True, True, False])
    full_metrics.to_parquet(out_dir / "long_sample_metrics.parquet", index=False)
    full_metrics.to_csv(out_dir / "long_sample_metrics.csv", index=False)
    walk_forward.to_parquet(out_dir / "long_sample_walk_forward.parquet", index=False)
    walk_forward.to_csv(out_dir / "long_sample_walk_forward.csv", index=False)
    latest_weights.to_parquet(out_dir / "long_sample_latest_weights.parquet", index=False)
    latest_weights.to_csv(out_dir / "long_sample_latest_weights.csv", index=False)
    return {"full_metrics": full_metrics, "walk_forward": walk_forward, "latest_weights": latest_weights}


def filter_dates(frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    return result[(result["date"] >= pd.Timestamp(start_date)) & (result["date"] <= pd.Timestamp(end_date))].reset_index(drop=True)


def filter_splits_with_data(
    daily: pd.DataFrame,
    splits: list[tuple[str, str, str, str, str]],
) -> list[tuple[str, str, str, str, str]]:
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    available = []
    for split in splits:
        _, train_start, train_end, test_start, test_end = split
        has_train = frame["date"].between(pd.Timestamp(train_start), pd.Timestamp(train_end)).any()
        has_test = frame["date"].between(pd.Timestamp(test_start), pd.Timestamp(test_end)).any()
        if has_train and has_test:
            available.append(split)
    return available


def data_availability(frame: pd.DataFrame) -> list[dict]:
    grouped = (
        frame.assign(date=pd.to_datetime(frame["date"]))
        .groupby("symbol")["date"]
        .agg(["min", "max", "count"])
        .reset_index()
        .sort_values("symbol")
    )
    grouped["min"] = grouped["min"].dt.date.astype(str)
    grouped["max"] = grouped["max"].dt.date.astype(str)
    return grouped.to_dict(orient="records")


def sanitize_json(value):
    if isinstance(value, dict):
        return {key: sanitize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


if __name__ == "__main__":
    main()
