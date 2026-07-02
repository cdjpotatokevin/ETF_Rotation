from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    top_n: int = 5
    rebalance_frequency: str = "W-FRI"
    transaction_cost_bps: float = 5.0
    max_single_weight: float = 0.25
    min_score: float | None = None


def build_weekly_weights(
    scores: pd.DataFrame,
    config: BacktestConfig,
) -> pd.DataFrame:
    dates = pd.to_datetime(scores["date"])
    score_frame = scores.copy()
    score_frame["date"] = dates
    rebalance_dates = select_rebalance_dates(score_frame, config.rebalance_frequency)
    rows: List[Dict[str, float]] = []

    for dt in rebalance_dates:
        day_scores = score_frame[score_frame["date"] == dt].sort_values("baseline_score", ascending=False)
        if config.min_score is not None:
            day_scores = day_scores[day_scores["baseline_score"] >= config.min_score]
        selected = day_scores.head(config.top_n)
        if selected.empty:
            continue
        equal_weight = min(1.0 / len(selected), config.max_single_weight)
        total_weight = equal_weight * len(selected)
        cash_weight = max(0.0, 1.0 - total_weight)
        for _, row in selected.iterrows():
            rows.append({"date": dt, "symbol": row["symbol"], "weight": equal_weight})
        if cash_weight:
            rows.append({"date": dt, "symbol": "CASH", "weight": cash_weight})

    return pd.DataFrame(rows, columns=["date", "symbol", "weight"])


def select_rebalance_dates(score_frame: pd.DataFrame, frequency: str) -> pd.Series:
    unique_dates = pd.Series(pd.to_datetime(score_frame["date"].unique())).sort_values()
    normalized = frequency.upper()
    if normalized == "W-FRI":
        return unique_dates[unique_dates.dt.dayofweek == 4]
    if normalized in {"M", "ME", "MONTHLY"}:
        return unique_dates.groupby(unique_dates.dt.to_period("M")).max().sort_values().reset_index(drop=True)
    raise ValueError(f"unsupported rebalance frequency: {frequency}")


def run_weekly_rotation_backtest(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    config: BacktestConfig,
) -> Dict[str, pd.DataFrame | Dict[str, float]]:
    prices = daily[["date", "symbol", "close"]].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    returns = prices.sort_values(["symbol", "date"])
    returns["asset_return"] = returns.groupby("symbol")["close"].pct_change().fillna(0.0)
    ret_pivot = returns.pivot(index="date", columns="symbol", values="asset_return").fillna(0.0)

    weights = build_weekly_weights(scores, config)
    weights_pivot = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    weights_pivot = weights_pivot.reindex(ret_pivot.index).ffill().fillna(0.0)
    asset_columns = [col for col in weights_pivot.columns if col != "CASH"]
    previous_weights = weights_pivot.shift(1).fillna(0.0)
    turnover = (weights_pivot[asset_columns] - previous_weights[asset_columns]).abs().sum(axis=1)
    cost = turnover * (config.transaction_cost_bps / 10_000)
    portfolio_return = (weights_pivot[asset_columns] * ret_pivot.reindex(columns=asset_columns).fillna(0.0)).sum(axis=1) - cost

    benchmark_return = ret_pivot[benchmark_symbol] if benchmark_symbol in ret_pivot else pd.Series(0.0, index=ret_pivot.index)
    equity = (1 + portfolio_return).cumprod()
    benchmark_equity = (1 + benchmark_return).cumprod()
    curve = pd.DataFrame(
        {
            "date": ret_pivot.index,
            "portfolio_return": portfolio_return.values,
            "benchmark_return": benchmark_return.values,
            "turnover": turnover.values,
            "equity": equity.values,
            "benchmark_equity": benchmark_equity.values,
        }
    )
    metrics = calculate_metrics(curve)
    return {"weights": weights, "curve": curve, "metrics": metrics}


def run_weighted_backtest(
    daily: pd.DataFrame,
    weights: pd.DataFrame,
    benchmark_symbol: str,
    transaction_cost_bps: float = 5.0,
) -> Dict[str, pd.DataFrame | Dict[str, float]]:
    prices = daily[["date", "symbol", "close"]].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    returns = prices.sort_values(["symbol", "date"])
    returns["asset_return"] = returns.groupby("symbol")["close"].pct_change().fillna(0.0)
    ret_pivot = returns.pivot(index="date", columns="symbol", values="asset_return").fillna(0.0)

    weights = weights.copy()
    weights["date"] = pd.to_datetime(weights["date"])
    weights_pivot = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    weights_pivot = weights_pivot.reindex(ret_pivot.index).ffill().fillna(0.0)
    asset_columns = [col for col in weights_pivot.columns if col != "CASH"]
    previous_weights = weights_pivot.shift(1).fillna(0.0)
    turnover = (weights_pivot[asset_columns] - previous_weights[asset_columns]).abs().sum(axis=1)
    cost = turnover * (transaction_cost_bps / 10_000)
    portfolio_return = (weights_pivot[asset_columns] * ret_pivot.reindex(columns=asset_columns).fillna(0.0)).sum(axis=1) - cost

    benchmark_return = ret_pivot[benchmark_symbol] if benchmark_symbol in ret_pivot else pd.Series(0.0, index=ret_pivot.index)
    equity = (1 + portfolio_return).cumprod()
    benchmark_equity = (1 + benchmark_return).cumprod()
    curve = pd.DataFrame(
        {
            "date": ret_pivot.index,
            "portfolio_return": portfolio_return.values,
            "benchmark_return": benchmark_return.values,
            "turnover": turnover.values,
            "equity": equity.values,
            "benchmark_equity": benchmark_equity.values,
        }
    )
    return {"weights": weights, "curve": curve, "metrics": calculate_metrics(curve)}


def calculate_metrics(curve: pd.DataFrame) -> Dict[str, float]:
    returns = curve["portfolio_return"]
    benchmark = curve["benchmark_return"]
    equity = curve["equity"]
    benchmark_equity = curve["benchmark_equity"]
    trading_days = 252
    total_return = float(equity.iloc[-1] - 1)
    annual_return = float(equity.iloc[-1] ** (trading_days / max(len(curve), 1)) - 1)
    annual_vol = float(returns.std(ddof=0) * np.sqrt(trading_days))
    sharpe = float(annual_return / annual_vol) if annual_vol else 0.0
    drawdown = equity / equity.cummax() - 1
    max_drawdown = float(drawdown.min())
    benchmark_total_return = float(benchmark_equity.iloc[-1] - 1)
    excess_total_return = total_return - benchmark_total_return
    tracking_diff = returns - benchmark
    information_ratio = float((tracking_diff.mean() * trading_days) / (tracking_diff.std(ddof=0) * np.sqrt(trading_days))) if tracking_diff.std(ddof=0) else 0.0
    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "benchmark_total_return": benchmark_total_return,
        "excess_total_return": excess_total_return,
        "information_ratio": information_ratio,
        "avg_turnover": float(curve["turnover"].mean()),
    }
