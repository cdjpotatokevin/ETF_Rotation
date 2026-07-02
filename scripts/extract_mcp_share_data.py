from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

from etf_rotation.config import load_etf_pool, resolve_project_path


NODE_BIN = "/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
IFIND_SCRIPT = "/Users/sweethome/.codex/skills/ifind-finance-data/scripts/ifind.js"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract official ETF share-flow data via iFinD MCP")
    parser.add_argument("--start", default="2026-06-22")
    parser.add_argument("--end", default="2026-06-30")
    parser.add_argument("--output", default="data/raw/etf_mcp_share_changes_recent.parquet")
    parser.add_argument("--raw-dir", default="data/raw/mcp_share_raw")
    parser.add_argument("--from-raw", action="store_true", help="Rebuild parquet from previously saved raw MCP responses")
    parser.add_argument(
        "--windows",
        default=None,
        help="Comma-separated date windows like 2022-06-22:2022-06-30,2023-06-21:2023-06-30",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    assets = load_etf_pool()
    raw_dir = resolve_project_path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    windows = parse_windows(args.windows, args.start, args.end)
    for start, end in windows:
        window_key = f"{start}_{end}".replace("-", "")
        for asset in assets:
            raw_path = raw_dir / window_key / f"{asset.symbol}.json"
            if args.from_raw:
                if not raw_path.exists():
                    continue
                result = json.loads(raw_path.read_text(encoding="utf-8"))
            else:
                print(f"query {asset.symbol} {start} {end}", flush=True)
                result = query_share_data(asset.symbol, start, end, timeout=args.timeout)
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(
                    json.dumps(redact_unneeded(result), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            parsed = parse_answer_rows(result, asset.symbol)
            for row in parsed:
                row["window_start"] = start
                row["window_end"] = end
            rows.extend(parsed)

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for column in ["exchange_share_change", "listed_trading_shares"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["date", "symbol"]).sort_values(["symbol", "date"])

    out = resolve_project_path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out, index=False)
    print(f"wrote {out}")
    print(f"rows={len(frame)} symbols={frame['symbol'].nunique() if not frame.empty else 0}")


def parse_windows(windows: str | None, start: str, end: str) -> List[tuple[str, str]]:
    if not windows:
        return [(start, end)]
    result = []
    for item in windows.split(","):
        left, right = item.split(":", 1)
        result.append((left.strip(), right.strip()))
    return result


def query_share_data(symbol: str, start: str, end: str, timeout: int = 60) -> Dict[str, Any]:
    query = (
        f"只查询证券代码{symbol}在{start}至{end}逐日的日期、"
        "当期场内流通份额变化、上市交易份额，输出每日明细表"
    )
    cmd = [
        NODE_BIN,
        IFIND_SCRIPT,
        "fund",
        "get_fund_ownership",
        json.dumps({"query": query}, ensure_ascii=False),
    ]
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def parse_answer_rows(result: Dict[str, Any], requested_symbol: str) -> List[Dict[str, Any]]:
    answer = extract_answer_text(result)
    fallback_date = extract_param_trade_date(answer)
    rows = []
    for table in markdown_tables(answer):
        if not table:
            continue
        header = table[0]
        if "证券代码" not in header:
            continue
        for cells in table[2:]:
            row = dict(zip(header, cells))
            symbol = row.get("证券代码", "").strip()
            if symbol != requested_symbol:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": row.get("证券简称", "").strip(),
                    "date": parse_date(row.get("日期", "") or fallback_date or ""),
                    "exchange_share_change": parse_cn_number(row.get("当期场内流通份额变化（单位：份）", "")),
                    "listed_trading_shares": parse_cn_number(row.get("上市交易份额（单位：份）", "")),
                    "source": "ifind_mcp",
                }
            )
    return rows


def extract_answer_text(result: Dict[str, Any]) -> str:
    content = result.get("data", {}).get("result", {}).get("content")
    if content is None:
        content = result.get("data", {}).get("result", {}).get("content", [])
    if not content:
        content = result.get("data", {}).get("result", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    payload = json.loads(text)
    return payload.get("data", {}).get("answer1", "")


def markdown_tables(text: str) -> Iterable[List[List[str]]]:
    current: List[List[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append([cell.strip() for cell in stripped.strip("|").split("|")])
        elif current:
            yield current
            current = []
    if current:
        yield current


def parse_date(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return value


def extract_param_trade_date(answer: str) -> str | None:
    marker = "```json"
    start = answer.find(marker)
    if start < 0:
        return None
    start = answer.find("{", start)
    end = answer.find("```", start)
    if start < 0 or end < 0:
        return None
    try:
        params = json.loads(answer[start:end])
    except json.JSONDecodeError:
        return None
    for item in params.values():
        trade_date = item.get("params", {}).get("交易日期") if isinstance(item, dict) else None
        if trade_date and trade_date != "最新":
            return parse_date(str(trade_date))
    return None


def parse_cn_number(value: Any) -> float | None:
    text = str(value).strip().replace(",", "")
    if not text or text == "\\t" or text == "-":
        return None
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10_000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def redact_unneeded(result: Dict[str, Any]) -> Dict[str, Any]:
    return result


if __name__ == "__main__":
    main()
