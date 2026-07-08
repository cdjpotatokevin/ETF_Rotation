from datetime import date

import pandas as pd

from etf_rotation.data.window import filter_daily_window


def test_filter_daily_window_keeps_configured_date_range():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2019-01-02", "2021-01-04", "2026-07-08", "2026-07-09"]),
            "symbol": ["A", "A", "A", "A"],
        }
    )

    filtered = filter_daily_window(daily, date(2021, 1, 1), date(2026, 7, 8))

    assert filtered["date"].tolist() == [pd.Timestamp("2021-01-04"), pd.Timestamp("2026-07-08")]
