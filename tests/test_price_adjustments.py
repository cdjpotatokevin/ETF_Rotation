import pandas as pd

from etf_rotation.data.adjustments import adjust_price_discontinuities, detect_price_discontinuities


def test_detect_price_discontinuities_flags_large_single_day_etf_jump():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-03", "2026-07-06", "2026-07-07"]),
            "symbol": ["159995.SZ", "159995.SZ", "159995.SZ"],
            "close": [3.0, 3.01, 1.50],
        }
    )

    events = detect_price_discontinuities(daily, threshold=0.35)

    assert len(events) == 1
    assert events.iloc[0]["symbol"] == "159995.SZ"
    assert events.iloc[0]["date"] == pd.Timestamp("2026-07-07")


def test_adjust_price_discontinuities_rebases_prior_trade_price_columns_only():
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-03", "2026-07-06", "2026-07-07", "2026-07-08"]),
            "symbol": ["159995.SZ"] * 4,
            "open": [2.9, 3.0, 1.48, 1.50],
            "high": [3.1, 3.1, 1.53, 1.55],
            "low": [2.8, 2.9, 1.46, 1.44],
            "close": [3.0, 3.01, 1.50, 1.49],
            "nav": [3.0, 1.50, 1.49, 1.48],
            "amount": [100.0, 110.0, 120.0, 130.0],
        }
    )

    adjusted = adjust_price_discontinuities(daily, threshold=0.35)

    before_split = adjusted[adjusted["date"] == pd.Timestamp("2026-07-06")].iloc[0]
    split_day = adjusted[adjusted["date"] == pd.Timestamp("2026-07-07")].iloc[0]
    assert abs(before_split["close"] - split_day["close"]) < 0.01
    assert before_split["nav"] == 1.50
    assert before_split["amount"] == 110.0
    assert split_day["amount"] == 120.0
