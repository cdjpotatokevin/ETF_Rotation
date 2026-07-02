from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import pandas as pd

from .models import ETF_DAILY_COLUMNS


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: List[str]
    warnings: List[str]

    def raise_for_errors(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def validate_etf_daily(frame: pd.DataFrame, expected_symbols: Iterable[str]) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    missing_cols = [col for col in ETF_DAILY_COLUMNS if col not in frame.columns]
    if missing_cols:
        errors.append(f"missing columns: {missing_cols}")
        return ValidationResult(False, errors, warnings)

    if frame.empty:
        errors.append("daily ETF frame is empty")
        return ValidationResult(False, errors, warnings)

    expected = set(expected_symbols)
    actual = set(frame["symbol"].dropna().unique())
    missing_symbols = sorted(expected - actual)
    if missing_symbols:
        errors.append(f"missing symbols: {missing_symbols}")

    duplicated = frame.duplicated(subset=["date", "symbol"]).sum()
    if duplicated:
        errors.append(f"duplicated date/symbol rows: {duplicated}")

    price_cols = ["open", "high", "low", "close"]
    if frame[price_cols].isna().any().any():
        errors.append("price columns contain null values")

    invalid_prices = (
        (frame["open"] <= 0)
        | (frame["high"] <= 0)
        | (frame["low"] <= 0)
        | (frame["close"] <= 0)
        | (frame["high"] < frame["low"])
    ).sum()
    if invalid_prices:
        errors.append(f"invalid OHLC rows: {int(invalid_prices)}")

    negative_volume = (frame["volume"] < 0).sum()
    if negative_volume:
        errors.append(f"negative volume rows: {int(negative_volume)}")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    obs_by_symbol = frame.groupby("symbol")["date"].nunique()
    low_obs = obs_by_symbol[obs_by_symbol < 120]
    if not low_obs.empty:
        warnings.append(f"symbols with fewer than 120 observations: {low_obs.to_dict()}")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)
