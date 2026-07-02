from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, build_weekly_weights, run_weighted_backtest


@dataclass(frozen=True)
class RiskControlConfig:
    portfolio_stop_loss: float | None = None
    target_vol: float | None = None
    vol_window: int = 63
    min_risk_scale: float = 0.3
    max_risk_scale: float = 1.0


def run_risk_controlled_backtest(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    backtest_config: BacktestConfig,
    risk_config: RiskControlConfig,
) -> dict:
    base_weights = build_weekly_weights(scores, backtest_config)
    adjusted_weights = apply_risk_controls(daily, scores, base_weights, backtest_config, risk_config)
    return run_weighted_backtest(
        daily=daily,
        weights=adjusted_weights,
        benchmark_symbol=benchmark_symbol,
        transaction_cost_bps=backtest_config.transaction_cost_bps,
    )


def apply_risk_controls(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    weights: pd.DataFrame,
    backtest_config: BacktestConfig,
    risk_config: RiskControlConfig,
) -> pd.DataFrame:
    if weights.empty:
        return weights
    dry_run = run_weighted_backtest(daily, weights, benchmark_symbol="")
    curve = dry_run["curve"].copy()
    curve["date"] = pd.to_datetime(curve["date"])
    curve["drawdown"] = curve["equity"] / curve["equity"].cummax() - 1
    curve["realized_vol"] = curve["portfolio_return"].rolling(risk_config.vol_window).std() * (252 ** 0.5)
    curve["risk_scale"] = 1.0
    if risk_config.target_vol:
        curve["risk_scale"] = (risk_config.target_vol / curve["realized_vol"]).clip(
            lower=risk_config.min_risk_scale,
            upper=risk_config.max_risk_scale,
        )
    curve["risk_scale"] = curve["risk_scale"].fillna(1.0)
    if risk_config.portfolio_stop_loss:
        stopped = curve["drawdown"] <= -abs(risk_config.portfolio_stop_loss)
        curve.loc[stopped, "risk_scale"] = 0.0

    weights = weights.copy()
    weights["date"] = pd.to_datetime(weights["date"])
    scale_by_date = curve.set_index("date")["risk_scale"]
    rows = []
    for dt, day in weights.groupby("date", sort=True):
        scale = float(scale_by_date.reindex([dt], method="ffill").iloc[0]) if dt in scale_by_date.index else 1.0
        asset_weight_sum = 0.0
        for _, row in day.iterrows():
            if row["symbol"] == "CASH":
                continue
            scaled = float(row["weight"]) * scale
            asset_weight_sum += scaled
            rows.append({"date": dt, "symbol": row["symbol"], "weight": scaled})
        cash_weight = max(0.0, 1.0 - asset_weight_sum)
        if cash_weight:
            rows.append({"date": dt, "symbol": "CASH", "weight": cash_weight})
    return pd.DataFrame(rows)
