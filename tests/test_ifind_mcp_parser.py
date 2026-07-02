import json

from etf_rotation.data.ifind_mcp import (
    extract_standard_tables,
    extract_text,
    markdown_table_rows,
    parse_cn_number,
)
from scripts.collect_ifind_research_data import date_windows, parse_macro_rows, parse_sector_index_rows


def wrapped(payload):
    return {
        "data": {
            "result": {
                "content": [
                    {
                        "text": json.dumps({"data": payload}, ensure_ascii=False),
                    }
                ]
            }
        }
    }


def test_extract_standard_tables_from_edb_payload():
    result = wrapped(
        {
            "answer": "|日期|制造业PMI（单位：%）|\n|---|---|\n|2026-06-30|50.3|",
            "datas": [
                {
                    "data": {
                        "columns": ["日期", "制造业PMI"],
                        "data": [["2026-06-30", 50.3]],
                        "attrs": {"制造业PMI": {"unit": "%", "index_id": "M002043802"}},
                    },
                    "source": "EDB",
                }
            ],
        }
    )
    tables = extract_standard_tables(result)
    assert tables[0]["columns"] == ["日期", "制造业PMI"]
    assert tables[0]["attrs"]["制造业PMI"]["unit"] == "%"


def test_parse_macro_rows_uses_standard_attrs():
    result = wrapped(
        {
            "datas": [
                {
                    "data": {
                        "columns": ["日期", "CPI:当月同比"],
                        "data": [["2026-05-31", 1.2]],
                        "attrs": {"CPI:当月同比": {"unit": "%", "index_id": "M002826730"}},
                    }
                }
            ]
        }
    )
    rows = parse_macro_rows(result, {"id": "cpi_yoy", "name": "CPI同比"}, "query")
    assert rows[0]["indicator_id"] == "cpi_yoy"
    assert rows[0]["value"] == 1.2
    assert rows[0]["ifind_index_id"] == "M002826730"


def test_markdown_table_rows_normalizes_unit_headers():
    rows = markdown_table_rows("|日期|成交金额（单位：元）|\n|---|---|\n|20260630|2329.7308亿|")
    assert rows == [{"日期": "20260630", "成交金额": "2329.7308亿"}]


def test_parse_sector_index_rows_converts_dates_and_amounts():
    result = wrapped(
        {
            "text": (
                "|证券代码|证券简称|日期|收盘价（单位：元）|成交金额（单位：元）|\n"
                "|---|---|---|---|---|\n"
                "|931865.CSI|中证半导|20260630|11350.2847|2329.7308亿|"
            )
        }
    )
    rows = parse_sector_index_rows(
        result,
        {"theme": "semiconductor", "name": "中证半导", "index_query": "中证全指半导体指数", "linked_etfs": ["159995.SZ"]},
        "query",
    )
    assert rows[0]["date"] == "2026-06-30"
    assert rows[0]["index_code"] == "931865.CSI"
    assert round(rows[0]["amount"]) == 232_973_080_000


def test_parse_cn_number_supports_chinese_units():
    assert parse_cn_number("1.4461万亿") == 1_446_100_000_000
    assert parse_cn_number("2329.7308亿") == 232_973_080_000


def test_date_windows_split_without_overlap():
    windows = date_windows("2026-01-01", "2026-06-30", 3)
    assert windows == [("2026-01-01", "2026-03-31"), ("2026-04-01", "2026-06-30")]
