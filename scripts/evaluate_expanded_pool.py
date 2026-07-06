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

from etf_rotation.config import load_etf_pool, load_project_config, resolve_project_path
from etf_rotation.data.ifind_http import IFindHttpMarketDataProvider
from etf_rotation.storage import ParquetStore
from scripts.compare_allocation_variants import DEFAULT_VARIANTS, latest_equity_exposure, to_candidate_config, variant_metadata
from scripts.validate_momentum_candidate import DEFAULT_SPLITS, compute_candidate_scores, prefix_metrics, run_candidate, run_walk_forward


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate current ETF pool versus expanded A-share ETF pool")
    parser.add_argument("--expanded-pool", default="config/etf_pool_expanded_a_share.json")
    parser.add_argument("--output-dir", default="data/processed/expanded_a_share_pool")
    parser.add_argument("--new-data-name", default="expanded_a_share_new_etf_daily")
    parser.add_argument("--fetch-missing", action="store_true")
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    cfg = load_project_config()
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_store = ParquetStore(cfg.raw_dir)

    base_daily = raw_store.read("etf_daily")
    expanded_assets = load_etf_pool(resolve_project_path(args.expanded_pool))
    base_symbols = set(base_daily["symbol"].unique())
    missing_assets = [asset for asset in expanded_assets if asset.symbol not in base_symbols]
    new_data_name = args.new_data_name

    if args.fetch_missing and missing_assets:
        fetched = IFindHttpMarketDataProvider().fetch_etf_daily(missing_assets, cfg.data_start, cfg.data_end)
        raw_store.write(new_data_name, fetched)

    new_daily = raw_store.read(new_data_name) if raw_store.exists(new_data_name) else pd.DataFrame(columns=base_daily.columns)
    expanded_daily = merge_existing_and_new_daily(base_daily, new_daily)
    expanded_daily.to_parquet(out_dir / "expanded_a_share_etf_daily.parquet", index=False)
    unavailable = missing_symbols(expanded_assets, expanded_daily)
    availability = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "base_symbol_count": int(base_daily["symbol"].nunique()),
        "expanded_symbol_count": int(expanded_daily["symbol"].nunique()),
        "missing_symbols_without_data": unavailable,
        "message": "扩展池历史行情数据已完整。" if not unavailable else "扩展池历史行情数据不完整，未运行扩展池回测。请配置 IFIND_REFRESH_TOKEN 或稍后重试 iFinD MCP。",
    }
    (out_dir / "data_availability.json").write_text(json.dumps(availability, ensure_ascii=False, indent=2), encoding="utf-8")
    if unavailable and not args.allow_incomplete:
        raise SystemExit(json.dumps(availability, ensure_ascii=False, indent=2))

    summary = compare_pools(base_daily, expanded_daily, cfg.benchmark_symbol, out_dir)
    summary_payload = {
        "benchmark_symbol": cfg.benchmark_symbol,
        "base_symbol_count": int(base_daily["symbol"].nunique()),
        "expanded_symbol_count": int(expanded_daily["symbol"].nunique()),
        "missing_symbols_without_data": unavailable,
        "full_metrics": summary["full_metrics"].to_dict(orient="records"),
        "walk_forward": summary["walk_forward"].to_dict(orient="records"),
        "latest_weights": summary["latest_weights"].to_dict(orient="records"),
    }
    (out_dir / "summary.json").write_text(json.dumps(sanitize_json(summary_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(sanitize_json(summary_payload), ensure_ascii=False, indent=2))


def merge_existing_and_new_daily(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if new.empty:
        return existing.copy()
    existing_frame = existing.copy()
    new_frame = new.copy()
    existing_frame["date"] = pd.to_datetime(existing_frame["date"])
    new_frame["date"] = pd.to_datetime(new_frame["date"])
    replacement_symbols = set(new_frame["symbol"].dropna().unique())
    kept_existing = existing_frame[~existing_frame["symbol"].isin(replacement_symbols)]
    merged = pd.concat([kept_existing, new_frame], ignore_index=True, sort=False)
    return merged.sort_values(["symbol", "date"]).reset_index(drop=True)


def missing_symbols(assets: list, daily: pd.DataFrame) -> list[str]:
    available = set(daily["symbol"].dropna().unique()) if "symbol" in daily else set()
    return sorted(asset.symbol for asset in assets if asset.symbol not in available)


def compare_pools(base_daily: pd.DataFrame, expanded_daily: pd.DataFrame, benchmark_symbol: str, out_dir: Path) -> dict:
    rows = []
    walk_rows = []
    latest_rows = []
    weights_by_pool = {}
    pools = [
        ("base_pool", "原19只ETF池", base_daily),
        ("expanded_pool", "扩展A股ETF池", expanded_daily),
    ]
    for pool_key, pool_name, daily in pools:
        scores = compute_candidate_scores(daily, "m_1_3_6")
        for variant in DEFAULT_VARIANTS:
            candidate = to_candidate_config(variant)
            result = run_candidate(daily, scores, benchmark_symbol, candidate)
            weights = result["weights"].copy()
            curve = result["curve"].copy()
            weights_by_pool[(pool_key, variant.key)] = weights
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

            walk = run_walk_forward(daily, scores, benchmark_symbol, candidate, DEFAULT_SPLITS)
            for record in walk.to_dict(orient="records"):
                walk_rows.append({"pool_key": pool_key, "pool_name": pool_name, **variant_metadata(variant), **record})

    full_metrics = pd.DataFrame(rows).sort_values(["key", "pool_key"])
    walk_forward = pd.DataFrame(walk_rows).sort_values(["key", "pool_key", "split"])
    latest_weights = pd.DataFrame(latest_rows).sort_values(["pool_key", "key", "weight"], ascending=[True, True, False])
    full_metrics.to_parquet(out_dir / "pool_comparison_metrics.parquet", index=False)
    full_metrics.to_csv(out_dir / "pool_comparison_metrics.csv", index=False)
    walk_forward.to_parquet(out_dir / "pool_comparison_walk_forward.parquet", index=False)
    walk_forward.to_csv(out_dir / "pool_comparison_walk_forward.csv", index=False)
    latest_weights.to_parquet(out_dir / "latest_pool_comparison_weights.parquet", index=False)
    latest_weights.to_csv(out_dir / "latest_pool_comparison_weights.csv", index=False)
    return {
        "full_metrics": full_metrics,
        "walk_forward": walk_forward,
        "latest_weights": latest_weights,
        "base_weights": weights_by_pool[("base_pool", "top3_cap25_cash")],
        "expanded_weights": weights_by_pool[("expanded_pool", "top3_cap25_cash")],
    }


def latest_weight_rows(
    weights: pd.DataFrame,
    daily: pd.DataFrame,
    pool_key: str,
    pool_name: str,
    variant_key: str = "top3_cap25_cash",
    variant_name: str = "Top3 单只25%上限，剩余现金",
) -> list[dict]:
    if weights.empty:
        return []
    frame = weights.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    latest = frame["date"].max()
    names = symbol_names(daily)
    rows = []
    for _, row in frame[frame["date"] == latest].iterrows():
        symbol = row["symbol"]
        rows.append(
            {
                "pool_key": pool_key,
                "pool_name": pool_name,
                "key": variant_key,
                "variant_name": variant_name,
                "date": latest.date().isoformat(),
                "symbol": symbol,
                "asset_name": "现金" if symbol == "CASH" else names.get(symbol, ""),
                "weight": float(row["weight"]),
            }
        )
    return rows


def symbol_names(daily: pd.DataFrame) -> dict[str, str]:
    if "name" not in daily:
        return {}
    return daily.dropna(subset=["symbol"]).drop_duplicates("symbol").set_index("symbol")["name"].to_dict()


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
