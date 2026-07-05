from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, build_weekly_weights, run_weighted_backtest, select_rebalance_dates
from etf_rotation.ml import Standardizer, build_ml_feature_frame, fit_logistic


REGIME_FEATURES = [
    "selected_count",
    "avg_score",
    "min_score",
    "score_spread",
    "avg_raw_momentum",
    "avg_ret_21d",
    "avg_ret_63d",
    "avg_ret_126d",
    "avg_vol_63d",
    "avg_drawdown_63d",
    "avg_relative_strength_21d",
    "benchmark_ret_21d",
    "benchmark_ret_63d",
    "benchmark_vol_63d",
    "benchmark_drawdown_63d",
]


@dataclass(frozen=True)
class MLRegimeOverlayConfig:
    probability_threshold: float = 0.55
    top_n: int = 3
    min_score: float | None = 0.60
    defensive_weight: float = 0.25
    full_weight: float = 1.0 / 3.0
    transaction_cost_bps: float = 5.0
    rebalance_frequency: str = "W-FRI"


def build_regime_decision_frame(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    top_n: int = 3,
    min_score: float | None = 0.60,
    rebalance_frequency: str = "W-FRI",
) -> pd.DataFrame:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"])
    feature_frame = build_ml_feature_frame(daily, benchmark_symbol, horizon=21)
    feature_frame["date"] = pd.to_datetime(feature_frame["date"])
    price_pivot = daily.pivot(index="date", columns="symbol", values="close").sort_index()
    rebalance_dates = list(select_rebalance_dates(scores, rebalance_frequency))
    rows = []

    for idx, dt in enumerate(rebalance_dates):
        day_scores = scores[scores["date"] == dt].sort_values("baseline_score", ascending=False)
        if min_score is not None:
            day_scores = day_scores[day_scores["baseline_score"] >= min_score]
        selected = day_scores.head(top_n).copy()
        selected_symbols = list(selected["symbol"])
        selected_features = feature_frame[(feature_frame["date"] == dt) & (feature_frame["symbol"].isin(selected_symbols))]
        benchmark_features = feature_frame[(feature_frame["date"] == dt) & (feature_frame["symbol"] == benchmark_symbol)]
        next_dt = rebalance_dates[idx + 1] if idx + 1 < len(rebalance_dates) else None
        basket_forward_return = selected_basket_return(price_pivot, dt, next_dt, selected_symbols)
        row = {
            "date": dt,
            "selected_symbols": ",".join(selected_symbols),
            "basket_forward_return": basket_forward_return,
            "target_full": float(basket_forward_return > 0) if pd.notna(basket_forward_return) else np.nan,
            "selected_count": float(len(selected_symbols)),
            "avg_score": float(selected["baseline_score"].mean()) if not selected.empty else 0.0,
            "min_score": float(selected["baseline_score"].min()) if not selected.empty else 0.0,
            "score_spread": float(selected["baseline_score"].max() - selected["baseline_score"].min()) if len(selected) > 1 else 0.0,
            **aggregate_selected_features(selected_features),
            **benchmark_regime_features(benchmark_features),
        }
        rows.append(row)

    result = pd.DataFrame(rows)
    for column in REGIME_FEATURES:
        if column not in result:
            result[column] = 0.0
    result[REGIME_FEATURES] = result[REGIME_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return result.sort_values("date").reset_index(drop=True)


def aggregate_selected_features(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "avg_raw_momentum": 0.0,
            "avg_ret_21d": 0.0,
            "avg_ret_63d": 0.0,
            "avg_ret_126d": 0.0,
            "avg_vol_63d": 0.0,
            "avg_drawdown_63d": 0.0,
            "avg_relative_strength_21d": 0.0,
        }
    return {
        "avg_raw_momentum": float(frame["raw_momentum"].mean()),
        "avg_ret_21d": float(frame["ret_21d"].mean()),
        "avg_ret_63d": float(frame["ret_63d"].mean()),
        "avg_ret_126d": float(frame["ret_126d"].mean()),
        "avg_vol_63d": float(frame["vol_63d"].mean()),
        "avg_drawdown_63d": float(frame["drawdown_63d"].mean()),
        "avg_relative_strength_21d": float(frame["relative_strength_21d"].mean()),
    }


def benchmark_regime_features(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {"benchmark_ret_21d": 0.0, "benchmark_ret_63d": 0.0, "benchmark_vol_63d": 0.0, "benchmark_drawdown_63d": 0.0}
    row = frame.iloc[0]
    return {
        "benchmark_ret_21d": float(row.get("ret_21d", 0.0)),
        "benchmark_ret_63d": float(row.get("ret_63d", 0.0)),
        "benchmark_vol_63d": float(row.get("vol_63d", 0.0)),
        "benchmark_drawdown_63d": float(row.get("drawdown_63d", 0.0)),
    }


def selected_basket_return(price_pivot: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None, symbols: Iterable[str]) -> float:
    symbols = [symbol for symbol in symbols if symbol in price_pivot.columns]
    if end is None or not symbols or start not in price_pivot.index or end not in price_pivot.index:
        return np.nan
    start_prices = price_pivot.loc[start, symbols].replace(0, np.nan)
    end_prices = price_pivot.loc[end, symbols]
    returns = end_prices / start_prices - 1.0
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
    return float(returns.mean()) if not returns.empty else np.nan


def fit_regime_model(train: pd.DataFrame, alpha: float = 2.0):
    fitted = train.dropna(subset=["target_full"]).copy()
    return fit_logistic(fitted, REGIME_FEATURES, target_column="target_full", alpha=alpha, learning_rate=0.05, iterations=800)


def predict_regime_probabilities(model, frame: pd.DataFrame) -> pd.DataFrame:
    result = frame[["date"]].copy()
    result["prob_full"] = model.predict_proba(frame)
    return result


def build_ml_regime_weights(scores: pd.DataFrame, probabilities: pd.DataFrame, config: MLRegimeOverlayConfig) -> pd.DataFrame:
    scores = scores.copy()
    scores["date"] = pd.to_datetime(scores["date"])
    probabilities = probabilities.copy()
    probabilities["date"] = pd.to_datetime(probabilities["date"])
    prob_by_date = probabilities.drop_duplicates("date").set_index("date")["prob_full"].sort_index()
    rows = []
    rebalance_dates = select_rebalance_dates(scores, config.rebalance_frequency)
    for dt in rebalance_dates:
        day_scores = scores[scores["date"] == dt].sort_values("baseline_score", ascending=False)
        if config.min_score is not None:
            day_scores = day_scores[day_scores["baseline_score"] >= config.min_score]
        selected = day_scores.head(config.top_n)
        if selected.empty:
            continue
        prob = float(prob_by_date.reindex([dt], method="ffill").iloc[0]) if not prob_by_date.empty else 0.0
        weight = config.full_weight if prob >= config.probability_threshold else config.defensive_weight
        for _, row in selected.iterrows():
            rows.append({"date": dt, "symbol": row["symbol"], "weight": weight, "prob_full": prob})
        cash_weight = max(0.0, 1.0 - weight * len(selected))
        if cash_weight:
            rows.append({"date": dt, "symbol": "CASH", "weight": cash_weight, "prob_full": prob})
    return pd.DataFrame(rows, columns=["date", "symbol", "weight", "prob_full"])


def run_ml_regime_overlay_backtest(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    probabilities: pd.DataFrame,
    benchmark_symbol: str,
    config: MLRegimeOverlayConfig,
) -> dict:
    weights = build_ml_regime_weights(scores, probabilities, config)
    return run_weighted_backtest(daily, weights[["date", "symbol", "weight"]], benchmark_symbol, transaction_cost_bps=config.transaction_cost_bps)


def static_allocation_result(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    benchmark_symbol: str,
    top_n: int,
    min_score: float | None,
    max_single_weight: float,
    transaction_cost_bps: float,
) -> dict:
    config = BacktestConfig(top_n=top_n, min_score=min_score, max_single_weight=max_single_weight, transaction_cost_bps=transaction_cost_bps)
    return run_weighted_backtest(
        daily,
        build_weekly_weights(scores, config),
        benchmark_symbol,
        transaction_cost_bps=transaction_cost_bps,
    )
