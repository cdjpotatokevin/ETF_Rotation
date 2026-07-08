from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.config import load_etf_pool, load_project_config, resolve_project_path
from etf_rotation.data.adjustments import adjust_price_discontinuities, detect_price_discontinuities
from etf_rotation.data.ifind_http import IFindHttpMarketDataProvider
from etf_rotation.storage import ParquetStore
from etf_rotation.validation import validate_etf_daily


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally refresh iFinD ETF daily data")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--expanded-pool", default="config/etf_pool_expanded_a_share.json")
    parser.add_argument("--expanded-new-name", default="expanded_a_share_new_etf_daily")
    parser.add_argument("--update-project-config", action="store_true")
    args = parser.parse_args()

    cfg = load_project_config()
    start = date.fromisoformat(args.start_date) if args.start_date else None
    end = date.fromisoformat(args.end_date)
    store = ParquetStore(cfg.raw_dir)
    provider = IFindHttpMarketDataProvider()

    base_assets = load_etf_pool()
    base = store.read("etf_daily")
    base_updated, base_fetch_summary = refresh_frame(provider, base, base_assets, end, start=start)
    validate_etf_daily(base_updated, [asset.symbol for asset in base_assets]).raise_for_errors()
    store.write("etf_daily", base_updated)

    expanded_assets = load_etf_pool(resolve_project_path(args.expanded_pool))
    base_symbols = {asset.symbol for asset in base_assets}
    extra_assets = [asset for asset in expanded_assets if asset.symbol not in base_symbols]
    expanded_new = store.read(args.expanded_new_name) if store.exists(args.expanded_new_name) else pd.DataFrame(columns=base.columns)
    expanded_updated, expanded_fetch_summary = refresh_frame(provider, expanded_new, extra_assets, end, start=start)
    store.write(args.expanded_new_name, expanded_updated)

    if args.update_project_config:
        update_project_data_end(resolve_project_path("config/project.json"), max_data_date(base_updated, expanded_updated))

    summary = {
        "requested_start": start.isoformat() if start else None,
        "requested_end": end.isoformat(),
        "base": base_fetch_summary,
        "expanded_new": expanded_fetch_summary,
        "base_max_date": max_data_date(base_updated).isoformat(),
        "expanded_new_max_date": max_data_date(expanded_updated).isoformat(),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def refresh_frame(
    provider: IFindHttpMarketDataProvider,
    existing: pd.DataFrame,
    assets: list,
    end: date,
    start: date | None = None,
) -> tuple[pd.DataFrame, dict]:
    if not assets:
        return existing, {"fetched_rows": 0, "symbols": 0, "start": None, "end": None, "mode": "noop"}

    fetch_ranges = []
    if existing.empty:
        fetch_start = start or end
        fetch_ranges.append((fetch_start, end))
    else:
        existing = existing.copy()
        existing["date"] = pd.to_datetime(existing["date"])
        min_existing = existing["date"].min().date()
        max_existing = existing["date"].max().date()
        if start and start < min_existing:
            fetch_ranges.append((start, min_existing - timedelta(days=1)))
        forward_start = max_existing + timedelta(days=1)
        if forward_start <= end:
            fetch_ranges.append((forward_start, end))

    fetch_ranges = [(fetch_start, fetch_end) for fetch_start, fetch_end in fetch_ranges if fetch_start <= fetch_end]
    if not fetch_ranges:
        return existing, {"fetched_rows": 0, "symbols": len(assets), "start": None, "end": None, "mode": "noop"}

    fetched_frames = [provider.fetch_etf_daily(assets, fetch_start, fetch_end) for fetch_start, fetch_end in fetch_ranges]
    non_empty_fetched = [frame for frame in fetched_frames if not frame.empty]
    fetched = pd.concat(non_empty_fetched, ignore_index=True) if non_empty_fetched else pd.DataFrame()
    if fetched.empty:
        return existing, {
            "fetched_rows": 0,
            "symbols": len(assets),
            "start": fetch_ranges[0][0].isoformat(),
            "end": fetch_ranges[-1][1].isoformat(),
            "mode": fetch_mode(fetch_ranges, existing),
        }
    merged = merge_daily(existing, fetched)
    events = detect_price_discontinuities(merged)
    merged = adjust_price_discontinuities(merged)
    return merged, {
        "fetched_rows": int(len(fetched)),
        "fetched_symbols": int(fetched["symbol"].nunique()),
        "adjustment_events": int(len(events)),
        "adjusted_symbols": sorted(events["symbol"].unique().tolist()) if not events.empty else [],
        "symbols": len(assets),
        "start": fetch_ranges[0][0].isoformat(),
        "end": fetch_ranges[-1][1].isoformat(),
        "mode": fetch_mode(fetch_ranges, existing),
        "fetched_min_date": str(pd.to_datetime(fetched["date"]).min().date()),
        "fetched_max_date": str(pd.to_datetime(fetched["date"]).max().date()),
    }


def fetch_mode(fetch_ranges: list[tuple[date, date]], existing: pd.DataFrame) -> str:
    if existing.empty:
        return "initial"
    existing_dates = pd.to_datetime(existing["date"])
    min_existing = existing_dates.min().date()
    max_existing = existing_dates.max().date()
    has_backfill = any(fetch_start < min_existing for fetch_start, _ in fetch_ranges)
    has_forward = any(fetch_end > max_existing for _, fetch_end in fetch_ranges)
    if has_backfill and has_forward:
        return "backfill+incremental"
    if has_backfill:
        return "backfill"
    if has_forward:
        return "incremental"
    return "noop"


def merge_daily(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    frames = [frame.copy() for frame in (existing, fetched) if not frame.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.sort_values(["symbol", "date"]).drop_duplicates(["date", "symbol"], keep="last")
    return merged.reset_index(drop=True)


def max_data_date(*frames: pd.DataFrame) -> date:
    dates = [pd.to_datetime(frame["date"]).max().date() for frame in frames if not frame.empty]
    return max(dates)


def update_project_data_end(path: Path, data_end: date) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["data_end"] = data_end.isoformat()
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
