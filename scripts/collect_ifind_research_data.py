from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

from etf_rotation.config import load_project_config, resolve_project_path
from etf_rotation.data.ifind_mcp import (
    extract_standard_tables,
    extract_text,
    markdown_table_rows,
    parse_cn_number,
)


NODE_BIN = "/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
IFIND_SCRIPT = "/Users/sweethome/.codex/skills/ifind-finance-data/scripts/ifind.js"
SECTOR_FUNDAMENTAL_COLUMNS = [
    "report_date",
    "theme",
    "sector_name",
    "sector_code",
    "metric",
    "value",
    "raw_value",
    "query",
    "source",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect macro and sector research data through iFinD MCP")
    parser.add_argument("--macro-config", default="config/macro_indicators.json")
    parser.add_argument("--sector-config", default="config/sector_indices.json")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--raw-dir", default="data/raw/ifind_research_raw")
    parser.add_argument("--datasets", default="macro,sector_index,sector_fundamental")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--report-date", default="2025-12-31")
    parser.add_argument("--sector-window-months", type=int, default=3)
    parser.add_argument("--refresh", action="store_true", help="Ignore existing raw responses and query iFinD again")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    project = load_project_config()
    start = args.start or project.data_start.isoformat()
    end = args.end or project.data_end.isoformat()
    datasets = {item.strip() for item in args.datasets.split(",") if item.strip()}
    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = resolve_project_path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {"start": start, "end": end, "datasets": sorted(datasets)}

    if "macro" in datasets:
        macro_rows = collect_macro(load_json(args.macro_config)["indicators"], start, end, raw_dir, args.timeout, args.refresh)
        macro = pd.DataFrame(macro_rows)
        if not macro.empty:
            macro["date"] = pd.to_datetime(macro["date"], errors="coerce")
            macro["value"] = pd.to_numeric(macro["value"], errors="coerce")
            macro = macro.dropna(subset=["date", "indicator_id", "value"]).sort_values(["indicator_id", "date"])
        macro.to_parquet(out_dir / "macro_indicators.parquet", index=False)
        summary["macro_rows"] = len(macro)
        summary["macro_indicators"] = int(macro["indicator_id"].nunique()) if not macro.empty else 0

    if "sector_index" in datasets:
        sectors = load_json(args.sector_config)["sectors"]
        sector_rows = collect_sector_index(sectors, start, end, raw_dir, args.timeout, args.sector_window_months, args.refresh)
        sector_daily = pd.DataFrame(sector_rows)
        if not sector_daily.empty:
            sector_daily["date"] = pd.to_datetime(sector_daily["date"], errors="coerce")
            for column in ["close", "pct_change", "amount", "period_amount", "period_avg_amount"]:
                if column in sector_daily:
                    sector_daily[column] = pd.to_numeric(sector_daily[column], errors="coerce")
            sector_daily = (
                sector_daily.dropna(subset=["date", "theme"])
                .drop_duplicates(subset=["theme", "index_code", "date"], keep="last")
                .sort_values(["theme", "date"])
            )
        sector_daily.to_parquet(out_dir / "sector_index_daily.parquet", index=False)
        summary["sector_index_rows"] = len(sector_daily)
        summary["sector_index_themes"] = int(sector_daily["theme"].nunique()) if not sector_daily.empty else 0

    if "sector_fundamental" in datasets:
        sectors = load_json(args.sector_config)["sectors"]
        fundamental_rows = collect_sector_fundamentals(sectors, args.report_date, raw_dir, args.timeout, args.refresh)
        fundamentals = pd.DataFrame(fundamental_rows, columns=SECTOR_FUNDAMENTAL_COLUMNS)
        if not fundamentals.empty:
            fundamentals["report_date"] = pd.to_datetime(fundamentals["report_date"], errors="coerce")
            fundamentals = fundamentals.sort_values(["theme", "metric"])
        fundamentals.to_parquet(out_dir / "sector_fundamentals.parquet", index=False)
        summary["sector_fundamental_rows"] = len(fundamentals)
        summary["sector_fundamental_themes"] = int(fundamentals["theme"].nunique()) if not fundamentals.empty else 0

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def collect_macro(
    indicators: Iterable[Dict[str, Any]],
    start: str,
    end: str,
    raw_dir: Path,
    timeout: int,
    refresh: bool,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for indicator in indicators:
        query = f"{indicator['query']}，{start[:7]}至{end[:7]}"
        raw_path = raw_dir / "macro" / f"{indicator['id']}.json"
        print(f"macro {indicator['id']}", flush=True)
        result = load_or_query(raw_path, "edb", "get_edb_data", query, timeout, refresh)
        rows.extend(parse_macro_rows(result, indicator, query))
    return rows


def collect_sector_index(
    sectors: Iterable[Dict[str, Any]],
    start: str,
    end: str,
    raw_dir: Path,
    timeout: int,
    window_months: int,
    refresh: bool,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sector in sectors:
        for window_start, window_end in date_windows(start, end, window_months):
            entity = f"指数代码{sector['index_code']}" if sector.get("index_code") else sector["index_query"]
            query = f"{entity}在{window_start}至{window_end}每日收盘点位、涨跌幅、成交额"
            window_key = f"{window_start}_{window_end}".replace("-", "")
            raw_path = raw_dir / "sector_index" / window_key / f"{sector['theme']}.json"
            print(f"sector_index {sector['theme']} {window_start} {window_end}", flush=True)
            result = load_or_query(raw_path, "index", "index_data", query, timeout, refresh)
            rows.extend(parse_sector_index_rows(result, sector, query))
    return rows


def collect_sector_index_single_window(
    sectors: Iterable[Dict[str, Any]],
    start: str,
    end: str,
    raw_dir: Path,
    timeout: int,
    refresh: bool,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sector in sectors:
        entity = f"指数代码{sector['index_code']}" if sector.get("index_code") else sector["index_query"]
        query = f"{entity}在{start}至{end}每日收盘点位、涨跌幅、成交额"
        result = query_ifind("index", "index_data", query, timeout)
        write_raw(raw_dir / "sector_index" / f"{sector['theme']}.json", result)
        rows.extend(parse_sector_index_rows(result, sector, query))
    return rows


def collect_sector_fundamentals(
    sectors: Iterable[Dict[str, Any]],
    report_date: str,
    raw_dir: Path,
    timeout: int,
    refresh: bool,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sector in sectors:
        query = (
            f"{sector.get('index_code') or sector['index_query']}在{report_date}的市盈率PE、市净率PB、ROE、"
            "预测净利润合计、预测EPS，输出板块代码和板块名称"
        )
        raw_path = raw_dir / "sector_fundamental" / f"{sector['theme']}.json"
        print(f"sector_fundamental {sector['theme']} {report_date}", flush=True)
        result = load_or_query(raw_path, "index", "sector_data", query, timeout, refresh)
        rows.extend(parse_sector_fundamental_rows(result, sector, query, report_date))
    return rows


def query_ifind(service: str, tool: str, query: str, timeout: int) -> Dict[str, Any]:
    cmd = [
        NODE_BIN,
        IFIND_SCRIPT,
        service,
        tool,
        json.dumps({"query": query}, ensure_ascii=False),
    ]
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def load_or_query(
    raw_path: Path,
    service: str,
    tool: str,
    query: str,
    timeout: int,
    refresh: bool,
) -> Dict[str, Any]:
    if raw_path.exists() and not refresh:
        return json.loads(raw_path.read_text(encoding="utf-8"))
    result = query_ifind(service, tool, query, timeout)
    write_raw(raw_path, result)
    return result


def parse_macro_rows(result: Dict[str, Any], indicator: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    rows = []
    for table in extract_standard_tables(result):
        columns = table["columns"]
        attrs = table.get("attrs", {})
        for values in table["rows"]:
            record = dict(zip(columns, values))
            date_value = record.get("日期") or record.get("指标日期")
            for metric, value in record.items():
                if metric in {"日期", "指标日期"}:
                    continue
                rows.append(
                    {
                        "date": date_value,
                        "indicator_id": indicator["id"],
                        "indicator_name": indicator["name"],
                        "metric": metric,
                        "value": value,
                        "unit": attrs.get(metric, {}).get("unit"),
                        "ifind_index_id": attrs.get(metric, {}).get("index_id") or table.get("extra", {}).get("index_id"),
                        "category": indicator.get("category"),
                        "frequency": indicator.get("frequency"),
                        "query": query,
                        "source": "ifind_mcp_edb",
                    }
                )
    if rows:
        return rows

    for record in markdown_table_rows(extract_text(result)):
        date_value = record.get("日期") or record.get("指标日期")
        for metric, value in record.items():
            if metric in {"日期", "指标日期"}:
                continue
            rows.append(
                {
                    "date": date_value,
                    "indicator_id": indicator["id"],
                    "indicator_name": indicator["name"],
                    "metric": metric,
                    "value": parse_cn_number(value),
                    "unit": None,
                    "ifind_index_id": None,
                    "category": indicator.get("category"),
                    "frequency": indicator.get("frequency"),
                    "query": query,
                    "source": "ifind_mcp_edb",
                }
            )
    return rows


def parse_sector_index_rows(result: Dict[str, Any], sector: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    rows = []
    for record in markdown_table_rows(extract_text(result)):
        date_value = record.get("日期")
        if not date_value:
            continue
        rows.append(
            {
                "date": parse_date(date_value),
                "theme": sector["theme"],
                "sector_name": sector["name"],
                "index_query": sector["index_query"],
                "index_code": record.get("证券代码"),
                "index_name": record.get("证券简称"),
                "close": parse_cn_number(record.get("收盘价")),
                "pct_change": parse_cn_number(record.get("涨跌幅")),
                "amount": parse_cn_number(record.get("成交金额") or record.get("成交额")),
                "period_amount": parse_cn_number(record.get("区间成交额")),
                "period_avg_amount": parse_cn_number(record.get("区间日均成交额")),
                "linked_etfs": ",".join(sector.get("linked_etfs", [])),
                "query": query,
                "source": "ifind_mcp_index",
            }
        )
    return rows


def parse_sector_fundamental_rows(
    result: Dict[str, Any],
    sector: Dict[str, Any],
    query: str,
    report_date: str,
) -> List[Dict[str, Any]]:
    rows = []
    for record in markdown_table_rows(extract_text(result)):
        sector_code = record.get("板块代码")
        sector_name = record.get("板块名称") or sector["name"]
        for metric, raw_value in record.items():
            if metric in {"板块代码", "板块名称"}:
                continue
            rows.append(
                {
                    "report_date": report_date,
                    "theme": sector["theme"],
                    "sector_name": sector_name,
                    "sector_code": sector_code,
                    "metric": metric,
                    "value": parse_cn_number(raw_value),
                    "raw_value": raw_value,
                    "query": query,
                    "source": "ifind_mcp_sector",
                }
            )
    return rows


def parse_date(value: Any) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return str(value)


def write_raw(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(resolve_project_path(path).read_text(encoding="utf-8"))


def date_windows(start: str, end: str, months: int) -> List[tuple[str, str]]:
    if months <= 0:
        return [(start, end)]
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    windows = []
    cursor = start_ts
    while cursor <= end_ts:
        window_end = min(cursor + pd.DateOffset(months=months) - pd.Timedelta(days=1), end_ts)
        windows.append((cursor.date().isoformat(), window_end.date().isoformat()))
        cursor = window_end + pd.Timedelta(days=1)
    return windows


if __name__ == "__main__":
    main()
