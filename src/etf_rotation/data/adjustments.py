from __future__ import annotations

import pandas as pd

PRICE_COLUMNS = ("open", "high", "low", "close")


def detect_price_discontinuities(
    daily: pd.DataFrame,
    *,
    threshold: float = 0.35,
    price_column: str = "close",
) -> pd.DataFrame:
    """Detect ETF price jumps that are more likely split/adjustment artifacts than market moves."""

    if daily.empty or price_column not in daily.columns:
        return pd.DataFrame(columns=["symbol", "date", "previous_close", "close", "ratio", "return"])

    frame = daily[["date", "symbol", price_column]].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["symbol", "date"])
    frame["previous_close"] = frame.groupby("symbol")[price_column].shift(1)
    frame = frame.dropna(subset=["previous_close", price_column])
    frame = frame[(frame["previous_close"] > 0) & (frame[price_column] > 0)].copy()
    frame["ratio"] = frame[price_column] / frame["previous_close"]
    frame["return"] = frame["ratio"] - 1.0
    events = frame[frame["return"].abs() >= threshold].copy()
    events = events.rename(columns={price_column: "close"})
    return events[["symbol", "date", "previous_close", "close", "ratio", "return"]].reset_index(drop=True)


def adjust_price_discontinuities(
    daily: pd.DataFrame,
    *,
    threshold: float = 0.35,
    price_columns: tuple[str, ...] = PRICE_COLUMNS,
) -> pd.DataFrame:
    """Back-adjust historical price columns across large ETF split-like discontinuities."""

    if daily.empty:
        return daily.copy()

    adjusted = daily.copy()
    adjusted["date"] = pd.to_datetime(adjusted["date"])
    adjusted = adjusted.sort_values(["symbol", "date"]).reset_index(drop=True)
    events = detect_price_discontinuities(adjusted, threshold=threshold)
    usable_price_columns = [column for column in price_columns if column in adjusted.columns]

    for event in events.sort_values(["symbol", "date"]).itertuples(index=False):
        ratio = float(event.ratio)
        if ratio <= 0:
            continue
        mask = (adjusted["symbol"] == event.symbol) & (adjusted["date"] < event.date)
        adjusted.loc[mask, usable_price_columns] = adjusted.loc[mask, usable_price_columns] * ratio

    return adjusted.reset_index(drop=True)
