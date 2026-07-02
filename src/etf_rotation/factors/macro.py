from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from etf_rotation.factors.common import cross_sectional_rank


MACRO_COLUMNS = {
    "pmi_mfg": "growth",
    "social_financing_yoy": "credit",
    "m2_yoy": "money",
    "cpi_yoy": "cpi",
    "ppi_yoy": "ppi",
    "cn_10y_yield": "rate",
}


THEME_EXPOSURES: Dict[str, Dict[str, float]] = {
    "technology": {"growth": 0.45, "liquidity": 0.45, "inflation": -0.10, "risk_off": -0.30},
    "semiconductor": {"growth": 0.50, "liquidity": 0.45, "inflation": -0.10, "risk_off": -0.35},
    "growth": {"growth": 0.45, "liquidity": 0.40, "inflation": -0.10, "risk_off": -0.30},
    "growth_leaders": {"growth": 0.45, "liquidity": 0.40, "inflation": -0.10, "risk_off": -0.30},
    "small_cap": {"growth": 0.35, "liquidity": 0.45, "inflation": -0.10, "risk_off": -0.25},
    "mid_cap": {"growth": 0.30, "liquidity": 0.30, "inflation": 0.00, "risk_off": -0.15},
    "consumer": {"growth": 0.10, "liquidity": 0.00, "inflation": -0.05, "risk_off": 0.25},
    "food_beverage": {"growth": 0.05, "liquidity": 0.00, "inflation": -0.05, "risk_off": 0.30},
    "pharmaceutical": {"growth": 0.05, "liquidity": 0.05, "inflation": -0.05, "risk_off": 0.30},
    "healthcare": {"growth": 0.05, "liquidity": 0.05, "inflation": -0.05, "risk_off": 0.30},
    "financial": {"growth": 0.20, "liquidity": -0.10, "inflation": 0.05, "risk_off": 0.05},
    "brokerage": {"growth": 0.35, "liquidity": 0.30, "inflation": 0.00, "risk_off": -0.20},
    "nonferrous_metals": {"growth": 0.35, "liquidity": 0.10, "inflation": 0.45, "risk_off": -0.20},
    "coal": {"growth": 0.20, "liquidity": 0.00, "inflation": 0.50, "risk_off": 0.00},
    "defense": {"growth": 0.05, "liquidity": 0.05, "inflation": 0.00, "risk_off": 0.20},
    "real_estate": {"growth": 0.30, "liquidity": 0.55, "inflation": -0.10, "risk_off": -0.25},
    "infrastructure": {"growth": 0.25, "liquidity": 0.25, "inflation": 0.20, "risk_off": 0.05},
    "large_cap": {"growth": 0.15, "liquidity": 0.05, "inflation": 0.00, "risk_off": 0.10},
    "dividend_low_vol": {"growth": -0.05, "liquidity": -0.05, "inflation": 0.15, "risk_off": 0.40},
}


def compute_macro_regime_components(macro: pd.DataFrame, dates: pd.Series | pd.DatetimeIndex) -> pd.DataFrame:
    frame = macro.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    pivot = (
        frame.pivot_table(index="date", columns="indicator_id", values="value", aggfunc="last")
        .sort_index()
        .rename(columns=MACRO_COLUMNS)
    )
    target_dates = pd.DatetimeIndex(pd.to_datetime(dates).unique()).sort_values()
    aligned = pivot.reindex(target_dates.union(pivot.index)).sort_index().ffill().reindex(target_dates)
    z = aligned.apply(rolling_zscore).fillna(0.0)

    growth = row_mean(z, ["growth", "credit", "money"]) - 0.35 * z.get("rate", 0.0)
    inflation = row_mean(z, ["cpi", "ppi"])
    liquidity = row_mean(z, ["money", "credit"]) - z.get("rate", 0.0)
    risk_off = -growth + 0.25 * z.get("rate", 0.0) + 0.15 * inflation

    return pd.DataFrame(
        {
            "date": target_dates,
            "macro_growth": growth.to_numpy(),
            "macro_inflation": inflation.to_numpy(),
            "macro_liquidity": liquidity.to_numpy(),
            "macro_risk_off": risk_off.to_numpy(),
        }
    )


def compute_macro_resonance(daily: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    assets = daily[["date", "symbol", "theme"]].copy()
    assets["date"] = pd.to_datetime(assets["date"])
    components = compute_macro_regime_components(macro, assets["date"])
    merged = assets.merge(components, on="date", how="left")
    merged["macro_raw_score"] = merged.apply(theme_macro_score, axis=1)
    ranked = cross_sectional_rank(merged, "macro_raw_score", "macro_resonance_score")
    return ranked[["date", "symbol", "macro_resonance_score", "macro_raw_score"]].sort_values(["date", "symbol"])


def theme_macro_score(row: pd.Series) -> float:
    exposures = THEME_EXPOSURES.get(str(row["theme"]), {})
    return float(
        exposures.get("growth", 0.0) * row.get("macro_growth", 0.0)
        + exposures.get("inflation", 0.0) * row.get("macro_inflation", 0.0)
        + exposures.get("liquidity", 0.0) * row.get("macro_liquidity", 0.0)
        + exposures.get("risk_off", 0.0) * row.get("macro_risk_off", 0.0)
    )


def rolling_zscore(series: pd.Series, window: int = 252, min_periods: int = 20) -> pd.Series:
    rolling = series.rolling(window=window, min_periods=min_periods)
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    z = (series - mean) / std.replace(0, np.nan)
    expanding_mean = series.expanding(min_periods=2).mean()
    expanding_std = series.expanding(min_periods=2).std(ddof=0).replace(0, np.nan)
    fallback = (series - expanding_mean) / expanding_std
    return z.fillna(fallback).fillna(0.0).clip(-3.0, 3.0)


def row_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series(0.0, index=frame.index)
    return frame[available].mean(axis=1)
