import json

from scripts.extract_mcp_share_data import parse_answer_rows


def test_parse_answer_rows():
    answer = (
        "|证券代码|证券简称|日期|当期场内流通份额变化（单位：份）|上市交易份额（单位：份）|\n"
        "|---|---|---|---|---|\n"
        "|512010.SH|医药ETF易方达|20260630|4.67亿|5.2117亿|\n"
        "|512010.SH|医药ETF易方达|20260629|-926000000.0|5.2117亿|\n"
    )
    result = {
        "data": {
            "result": {
                "content": [
                    {
                        "text": json.dumps({"data": {"answer1": answer}}, ensure_ascii=False),
                    }
                ]
            }
        }
    }
    rows = parse_answer_rows(result, "512010.SH")
    assert rows[0]["date"] == "2026-06-30"
    assert rows[0]["exchange_share_change"] == 467_000_000
    assert round(rows[0]["listed_trading_shares"]) == 521_170_000
    assert rows[1]["exchange_share_change"] == -926_000_000


def test_parse_answer_rows_with_param_date_fallback():
    answer = (
        "|证券代码|证券简称|当期场内流通份额变化（单位：份）|上市交易份额（单位：份）|\n"
        "|---|---|---|---|\n"
        "|510300.SH|沪深300ETF华泰柏瑞|-142200000.0|122.2969亿|\n\n"
        "```json\n"
        '{"当期场内流通份额变化":{"params":{"交易日期":"20260622","单位":" 份"},"unit":"份"}}'
        "\n```"
    )
    result = {
        "data": {
            "result": {
                "content": [
                    {
                        "text": json.dumps({"data": {"answer1": answer}}, ensure_ascii=False),
                    }
                ]
            }
        }
    }
    rows = parse_answer_rows(result, "510300.SH")
    assert rows[0]["date"] == "2026-06-22"
    assert rows[0]["exchange_share_change"] == -142_200_000
    assert round(rows[0]["listed_trading_shares"]) == 12_229_690_000
