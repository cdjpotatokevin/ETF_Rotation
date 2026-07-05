from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from etf_rotation.factors.common import cross_sectional_rank
from etf_rotation.factors.momentum_variants import MOMENTUM_SPECS, compute_momentum_variant


BASE_FEATURES = [
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "vol_21d",
    "vol_63d",
    "drawdown_63d",
    "amount_heat",
    "relative_strength_21d",
    "benchmark_ret_21d",
    "raw_momentum",
]

INTERACTION_FEATURES = [
    "ret_21d_x_ret_63d",
    "ret_63d_x_ret_126d",
    "raw_momentum_x_vol_63d",
    "relative_strength_21d_x_benchmark_ret_21d",
]


@dataclass(frozen=True)
class Standardizer:
    columns: list[str]
    mean: pd.Series
    std: pd.Series

    @classmethod
    def fit(cls, frame: pd.DataFrame, columns: Iterable[str]) -> "Standardizer":
        cols = list(columns)
        mean = frame[cols].mean()
        std = frame[cols].std(ddof=0).replace(0, np.nan).fillna(1.0)
        return cls(cols, mean, std)

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.columns].fillna(0.0)
        return ((values - self.mean) / self.std).to_numpy(dtype=float)


@dataclass(frozen=True)
class RidgeModel:
    standardizer: Standardizer
    coef: np.ndarray

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        x = add_intercept(self.standardizer.transform(frame))
        return x @ self.coef


@dataclass(frozen=True)
class LogisticModel:
    standardizer: Standardizer
    coef: np.ndarray

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        x = add_intercept(self.standardizer.transform(frame))
        return sigmoid(x @ self.coef)


def build_ml_feature_frame(daily: pd.DataFrame, benchmark_symbol: str, horizon: int = 21) -> pd.DataFrame:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values(["symbol", "date"])
    grouped = data.groupby("symbol")

    for window in (5, 21, 63, 126):
        data[f"ret_{window}d"] = grouped["close"].pct_change(window)

    data["vol_21d"] = grouped["close"].pct_change().groupby(data["symbol"]).rolling(21).std().reset_index(level=0, drop=True)
    data["vol_63d"] = grouped["close"].pct_change().groupby(data["symbol"]).rolling(63).std().reset_index(level=0, drop=True)
    rolling_high = grouped["close"].rolling(63, min_periods=5).max().reset_index(level=0, drop=True)
    data["drawdown_63d"] = data["close"] / rolling_high - 1.0
    amount_fast = grouped["amount"].rolling(21, min_periods=5).mean().reset_index(level=0, drop=True)
    amount_slow = grouped["amount"].rolling(63, min_periods=10).mean().reset_index(level=0, drop=True)
    data["amount_heat"] = amount_fast / amount_slow.replace(0, np.nan) - 1.0

    benchmark = (
        data[data["symbol"] == benchmark_symbol][["date", "ret_21d", "vol_63d"]]
        .rename(columns={"ret_21d": "benchmark_ret_21d", "vol_63d": "benchmark_vol_63d"})
        .sort_values("date")
    )
    data = data.merge(benchmark, on="date", how="left")
    data["relative_strength_21d"] = data["ret_21d"] - data["benchmark_ret_21d"]

    momentum = compute_momentum_variant(data, MOMENTUM_SPECS["m_1_3_6"])[["date", "symbol", "raw_momentum"]]
    data = data.merge(momentum, on=["date", "symbol"], how="left", suffixes=("", "_momentum"))
    if "raw_momentum_momentum" in data:
        data["raw_momentum"] = data["raw_momentum_momentum"]

    data["forward_return"] = grouped["close"].shift(-horizon) / data["close"] - 1.0
    data["forward_rank"] = data.groupby("date")["forward_return"].rank(pct=True)
    data["target_top"] = (data["forward_rank"] >= 0.70).astype(float)

    for column in BASE_FEATURES:
        if column not in data:
            data[column] = 0.0
    data[BASE_FEATURES] = data[BASE_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    add_interaction_features(data)
    return data[
        ["date", "symbol", "forward_return", "forward_rank", "target_top"]
        + BASE_FEATURES
        + INTERACTION_FEATURES
    ].sort_values(["date", "symbol"])


def add_interaction_features(frame: pd.DataFrame) -> None:
    frame["ret_21d_x_ret_63d"] = frame["ret_21d"] * frame["ret_63d"]
    frame["ret_63d_x_ret_126d"] = frame["ret_63d"] * frame["ret_126d"]
    frame["raw_momentum_x_vol_63d"] = frame["raw_momentum"] * frame["vol_63d"]
    frame["relative_strength_21d_x_benchmark_ret_21d"] = frame["relative_strength_21d"] * frame["benchmark_ret_21d"]
    frame[INTERACTION_FEATURES] = frame[INTERACTION_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)


def fit_ridge(train: pd.DataFrame, feature_columns: Iterable[str], target_column: str = "forward_return", alpha: float = 10.0) -> RidgeModel:
    fitted = train.dropna(subset=[target_column]).copy()
    standardizer = Standardizer.fit(fitted, feature_columns)
    x = add_intercept(standardizer.transform(fitted))
    y = fitted[target_column].to_numpy(dtype=float)
    penalty = np.eye(x.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.pinv(x.T @ x + penalty) @ x.T @ y
    return RidgeModel(standardizer, coef)


def fit_logistic(
    train: pd.DataFrame,
    feature_columns: Iterable[str],
    target_column: str = "target_top",
    alpha: float = 1.0,
    learning_rate: float = 0.05,
    iterations: int = 600,
) -> LogisticModel:
    fitted = train.dropna(subset=[target_column]).copy()
    standardizer = Standardizer.fit(fitted, feature_columns)
    x = add_intercept(standardizer.transform(fitted))
    y = fitted[target_column].to_numpy(dtype=float)
    coef = np.zeros(x.shape[1], dtype=float)
    for _ in range(iterations):
        pred = sigmoid(x @ coef)
        grad = x.T @ (pred - y) / max(len(y), 1)
        reg = alpha * coef / max(len(y), 1)
        reg[0] = 0.0
        coef -= learning_rate * (grad + reg)
    return LogisticModel(standardizer, coef)


def make_prediction_scores(predictions: pd.DataFrame, score_column: str = "prediction") -> pd.DataFrame:
    ranked = cross_sectional_rank(predictions, score_column, "baseline_score")
    return ranked[["date", "symbol", "baseline_score", score_column]].sort_values(["date", "symbol"])


def add_intercept(x: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x])


def sigmoid(x: np.ndarray) -> np.ndarray:
    clipped = np.clip(x, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))
