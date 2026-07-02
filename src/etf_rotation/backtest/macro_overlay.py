from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_rotation.backtest.engine import run_weighted_backtest
from etf_rotation.factors.macro import compute_macro_regime_components


@dataclass(frozen=True)
class MacroOverlayConfig:
    medium_risk_threshold: float = 0.35
    high_risk_threshold: float = 0.85
    medium_risk_exposure: float = 0.75
    high_risk_exposure: float = 0.50
    release_lag_days: int = 10


def compute_macro_overlay(macro: pd.DataFrame, dates: pd.Series | pd.DatetimeIndex, config: MacroOverlayConfig) -> pd.DataFrame:
    effective_macro = macro.copy()
    effective_macro["date"] = pd.to_datetime(effective_macro["date"]) + pd.Timedelta(days=config.release_lag_days)
    components = compute_macro_regime_components(effective_macro, pd.to_datetime(dates))
    components["macro_risk_score"] = (
        -0.45 * components["macro_growth"]
        - 0.35 * components["macro_liquidity"]
        + 0.15 * components["macro_inflation"]
        + 0.35 * components["macro_risk_off"]
    )
    components["target_exposure"] = 1.0
    components.loc[components["macro_risk_score"] >= config.medium_risk_threshold, "target_exposure"] = config.medium_risk_exposure
    components.loc[components["macro_risk_score"] >= config.high_risk_threshold, "target_exposure"] = config.high_risk_exposure
    return components[["date", "macro_risk_score", "target_exposure"]]


def apply_macro_overlay(weights: pd.DataFrame, overlay: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return weights
    adjusted = weights.copy()
    adjusted["date"] = pd.to_datetime(adjusted["date"])
    overlay = overlay.copy()
    overlay["date"] = pd.to_datetime(overlay["date"])
    exposure = overlay.set_index("date")["target_exposure"].sort_index()

    rows = []
    for dt, day in adjusted.groupby("date", sort=True):
        target = float(exposure.reindex([dt], method="ffill").iloc[0]) if not exposure.empty else 1.0
        asset_weight_sum = 0.0
        for _, row in day.iterrows():
            if row["symbol"] == "CASH":
                continue
            scaled = float(row["weight"]) * target
            asset_weight_sum += scaled
            rows.append({"date": dt, "symbol": row["symbol"], "weight": scaled})
        cash_weight = max(0.0, 1.0 - asset_weight_sum)
        if cash_weight:
            rows.append({"date": dt, "symbol": "CASH", "weight": cash_weight})
    return pd.DataFrame(rows, columns=["date", "symbol", "weight"])


def run_macro_overlay_backtest(
    daily: pd.DataFrame,
    weights: pd.DataFrame,
    macro: pd.DataFrame,
    benchmark_symbol: str,
    transaction_cost_bps: float,
    config: MacroOverlayConfig,
) -> dict:
    dates = pd.to_datetime(daily["date"])
    overlay = compute_macro_overlay(macro, dates, config)
    adjusted_weights = apply_macro_overlay(weights, overlay)
    result = run_weighted_backtest(daily, adjusted_weights, benchmark_symbol, transaction_cost_bps=transaction_cost_bps)
    result["overlay"] = overlay
    return result
