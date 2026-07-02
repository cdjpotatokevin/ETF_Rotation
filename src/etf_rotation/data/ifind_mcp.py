from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List


def extract_inner_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    content = result.get("data", {}).get("result", {}).get("content", [])
    if not content:
        return {}
    text = content[0].get("text", "")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return payload.get("data", payload)


def extract_text(result: Dict[str, Any]) -> str:
    payload = extract_inner_payload(result)
    for key in ("answer", "answer1", "text", "result"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def extract_standard_tables(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = extract_inner_payload(result)
    tables = []
    for item in payload.get("datas", []) or []:
        data = item.get("data") or {}
        columns = data.get("columns") or []
        rows = data.get("data") or []
        if columns and rows:
            tables.append(
                {
                    "columns": columns,
                    "rows": rows,
                    "attrs": data.get("attrs", {}),
                    "description": item.get("description", ""),
                    "source": item.get("source", ""),
                    "extra": item.get("extra", {}),
                }
            )
    return tables


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


def markdown_table_rows(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for table in markdown_tables(text):
        if len(table) < 3:
            continue
        header = [normalize_header(cell) for cell in table[0]]
        for cells in table[2:]:
            if len(cells) != len(header):
                continue
            rows.append(dict(zip(header, cells)))
    return rows


def normalize_header(value: str) -> str:
    return re.sub(r"（单位：[^）]+）", "", value).strip()


def parse_cn_number(value: Any) -> float | None:
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "nan", "None"}:
        return None
    multiplier = 1.0
    for suffix, scale in (("万亿", 1_000_000_000_000.0), ("亿", 100_000_000.0), ("万", 10_000.0)):
        if text.endswith(suffix):
            multiplier = scale
            text = text[: -len(suffix)]
            break
    try:
        return float(Decimal(text) * Decimal(str(multiplier)))
    except (InvalidOperation, ValueError):
        return None
