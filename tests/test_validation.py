import pandas as pd

from etf_rotation.models import ETF_DAILY_COLUMNS
from etf_rotation.validation import validate_etf_daily


def test_validation_rejects_missing_columns():
    result = validate_etf_daily(pd.DataFrame({"symbol": ["510300.SH"]}), ["510300.SH"])
    assert not result.ok
    assert "missing columns" in result.errors[0]


def test_validation_rejects_duplicate_rows():
    row = {
        "date": "2026-01-02",
        "symbol": "510300.SH",
        "name": "沪深300ETF",
        "bucket": "style",
        "theme": "large_cap",
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.0,
        "volume": 100,
        "amount": 100.0,
        "turnover": 1.0,
        "nav": 1.0,
        "premium_rate": 0.0,
        "shares_outstanding": 1000,
        "source": "test",
    }
    frame = pd.DataFrame([row, row])[ETF_DAILY_COLUMNS]
    result = validate_etf_daily(frame, ["510300.SH"])
    assert not result.ok
    assert any("duplicated" in err for err in result.errors)
