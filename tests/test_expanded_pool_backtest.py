from pathlib import Path

import pandas as pd

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from scripts.evaluate_expanded_pool import (
    compare_pools,
    missing_symbols,
    latest_weight_rows,
    merge_existing_and_new_daily,
)


def test_merge_existing_and_new_daily_replaces_duplicate_symbols():
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-02"]),
            "symbol": ["510300.SH", "588000.SH"],
            "close": [4.0, 1.0],
        }
    )
    new = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "symbol": ["588000.SH"],
            "close": [2.0],
        }
    )

    merged = merge_existing_and_new_daily(existing, new)

    assert len(merged) == 2
    assert merged.loc[merged["symbol"] == "588000.SH", "close"].iloc[0] == 2.0


def test_missing_symbols_reports_unavailable_expanded_assets():
    assets = load_etf_pool(Path("config/etf_pool_expanded_a_share.json"))
    daily = pd.DataFrame({"symbol": ["510300.SH", "515000.SH"]})

    missing = missing_symbols(assets, daily)

    assert "588000.SH" in missing
    assert "510300.SH" not in missing


def test_compare_pools_returns_latest_rows_with_codes_and_names(tmp_path):
    cfg = load_project_config()
    base_assets = load_etf_pool()[:6]
    extra_assets = load_etf_pool(Path("config/etf_pool_expanded_a_share.json"))[19:22]
    provider = SyntheticMarketDataProvider()
    base_daily = provider.fetch_etf_daily(base_assets, cfg.data_start, cfg.data_end)
    expanded_daily = provider.fetch_etf_daily(base_assets + extra_assets, cfg.data_start, cfg.data_end)

    summary = compare_pools(base_daily, expanded_daily, cfg.benchmark_symbol, tmp_path)

    assert {"base_pool", "expanded_pool"} <= set(summary["full_metrics"]["pool_key"])
    rows = latest_weight_rows(summary["expanded_weights"], expanded_daily, "expanded_pool", "扩展池")
    assert rows
    assert {"symbol", "asset_name", "weight"} <= set(rows[0])
