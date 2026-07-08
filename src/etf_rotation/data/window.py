from __future__ import annotations

from datetime import date

import pandas as pd


def filter_daily_window(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"])
    return result[(result["date"] >= pd.Timestamp(start)) & (result["date"] <= pd.Timestamp(end))].reset_index(drop=True)
