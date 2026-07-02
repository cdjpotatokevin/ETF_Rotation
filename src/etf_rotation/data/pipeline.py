from __future__ import annotations

from pathlib import Path

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.ifind_http import IFindHttpMarketDataProvider
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.storage import ParquetStore
from etf_rotation.validation import validate_etf_daily


def collect_daily(provider_name: str = "synthetic") -> Path:
    config = load_project_config()
    assets = load_etf_pool()
    if provider_name == "synthetic":
        provider = SyntheticMarketDataProvider()
    elif provider_name == "ifind-http":
        provider = IFindHttpMarketDataProvider()
    else:
        raise ValueError(f"unsupported provider: {provider_name}")
    frame = provider.fetch_etf_daily(assets, config.data_start, config.data_end)
    result = validate_etf_daily(frame, [asset.symbol for asset in assets])
    result.raise_for_errors()
    store = ParquetStore(config.raw_dir)
    return store.write("etf_daily", frame)


def validate_daily_file() -> dict:
    config = load_project_config()
    assets = load_etf_pool()
    store = ParquetStore(config.raw_dir)
    frame = store.read("etf_daily")
    result = validate_etf_daily(frame, [asset.symbol for asset in assets])
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "rows": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()) if "symbol" in frame else 0,
        "start": str(frame["date"].min()) if "date" in frame and not frame.empty else None,
        "end": str(frame["date"].max()) if "date" in frame and not frame.empty else None,
    }
