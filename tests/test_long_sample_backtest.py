from datetime import date

import pandas as pd

from etf_rotation.models import ETFAsset
from scripts.evaluate_long_sample import build_long_sample_splits, filter_splits_with_data
from scripts.refresh_ifind_incremental import refresh_frame


class FakeProvider:
    def fetch_etf_daily(self, assets, start, end):
        rows = []
        for asset in assets:
            rows.append(
                {
                    "date": start.isoformat(),
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "bucket": asset.bucket,
                    "theme": asset.theme,
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 100.0,
                    "amount": 100.0,
                    "turnover": 1.0,
                    "nav": 1.0,
                    "premium_rate": 0.0,
                    "shares_outstanding": 10000.0,
                    "source": "fake",
                }
            )
        return pd.DataFrame(rows)


class EmptyProvider:
    def fetch_etf_daily(self, assets, start, end):
        return pd.DataFrame()


def test_refresh_frame_can_backfill_before_existing_min_date():
    asset = ETFAsset("510300.SH", "沪深300ETF", "style", "large_cap")
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-04"]),
            "symbol": ["510300.SH"],
            "name": ["沪深300ETF"],
            "bucket": ["style"],
            "theme": ["large_cap"],
            "open": [2.0],
            "high": [2.0],
            "low": [2.0],
            "close": [2.0],
            "volume": [100.0],
            "amount": [200.0],
            "turnover": [1.0],
            "nav": [2.0],
            "premium_rate": [0.0],
            "shares_outstanding": [10000.0],
            "source": ["fixture"],
        }
    )

    updated, summary = refresh_frame(FakeProvider(), existing, [asset], date(2021, 1, 4), start=date(2019, 1, 1))

    assert pd.to_datetime(updated["date"]).min() == pd.Timestamp("2019-01-01")
    assert pd.to_datetime(updated["date"]).max() == pd.Timestamp("2021-01-04")
    assert summary["mode"] == "backfill"


def test_refresh_frame_handles_empty_fetch_response():
    asset = ETFAsset("510300.SH", "沪深300ETF", "style", "large_cap")
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-04"]),
            "symbol": ["510300.SH"],
            "name": ["沪深300ETF"],
            "bucket": ["style"],
            "theme": ["large_cap"],
            "open": [2.0],
            "high": [2.0],
            "low": [2.0],
            "close": [2.0],
            "volume": [100.0],
            "amount": [200.0],
            "turnover": [1.0],
            "nav": [2.0],
            "premium_rate": [0.0],
            "shares_outstanding": [10000.0],
            "source": ["fixture"],
        }
    )

    updated, summary = refresh_frame(EmptyProvider(), existing, [asset], date(2021, 1, 4), start=date(2019, 1, 1))

    assert len(updated) == 1
    assert summary["fetched_rows"] == 0
    assert summary["mode"] == "backfill"


def test_build_long_sample_splits_starts_from_first_year_after_training_window():
    splits = build_long_sample_splits("2019-01-01", "2026-07-08", train_end_year=2020)

    assert splits[0] == ("2021", "2019-01-01", "2020-12-31", "2021-01-01", "2021-12-31")
    assert splits[-1] == ("2026YTD", "2019-01-01", "2025-12-31", "2026-01-01", "2026-07-08")


def test_filter_splits_with_data_skips_empty_train_or_test_windows():
    daily = pd.DataFrame({"date": pd.to_datetime(["2021-06-30", "2022-01-04"])})
    splits = [
        ("2021", "2019-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
        ("2022", "2019-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
    ]

    filtered = filter_splits_with_data(daily, splits)

    assert filtered == [splits[1]]
