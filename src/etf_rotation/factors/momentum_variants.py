from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from etf_rotation.factors.common import cross_sectional_rank


@dataclass(frozen=True)
class MomentumSpec:
    name: str
    return_weights: Dict[int, float]
    vol_window: int = 63
    vol_penalty: float = 0.0
    trend_window: int | None = None
    trend_required: bool = False


def compute_momentum_variant(daily: pd.DataFrame, spec: MomentumSpec) -> pd.DataFrame:
    data = daily.sort_values(["symbol", "date"]).copy()
    grouped = data.groupby("symbol")["close"]
    raw = 0.0
    for window, weight in spec.return_weights.items():
        column = f"ret_{window}d"
        data[column] = grouped.pct_change(window)
        raw = raw + weight * data[column]
    if spec.vol_penalty:
        data["vol"] = grouped.pct_change().groupby(data["symbol"]).rolling(spec.vol_window).std().reset_index(level=0, drop=True)
        raw = raw - spec.vol_penalty * data["vol"].fillna(0)
    else:
        data["vol"] = grouped.pct_change().groupby(data["symbol"]).rolling(spec.vol_window).std().reset_index(level=0, drop=True)

    if spec.trend_window:
        trend_ma = grouped.transform(lambda s: s.rolling(spec.trend_window).mean())
        data["trend_ok"] = data["close"] >= trend_ma
        if spec.trend_required:
            raw = raw.where(data["trend_ok"], -1.0)
    else:
        data["trend_ok"] = True

    data["raw_momentum"] = raw
    ranked = cross_sectional_rank(data, "raw_momentum", "momentum_score")
    return ranked[["date", "symbol", "momentum_score", "raw_momentum", "vol", "trend_ok"]]


MOMENTUM_SPECS = {
    "m_1_3_6": MomentumSpec("m_1_3_6", {21: 0.35, 63: 0.40, 126: 0.25}, vol_penalty=0.20),
    "m_3_6": MomentumSpec("m_3_6", {63: 0.55, 126: 0.45}, vol_penalty=0.10),
    "m_6_12": MomentumSpec("m_6_12", {126: 0.60, 252: 0.40}, vol_penalty=0.10),
    "m_1_3": MomentumSpec("m_1_3", {21: 0.45, 63: 0.55}, vol_penalty=0.10),
    "m_3_6_trend": MomentumSpec("m_3_6_trend", {63: 0.55, 126: 0.45}, vol_penalty=0.10, trend_window=126, trend_required=True),
    "m_6_12_trend": MomentumSpec("m_6_12_trend", {126: 0.60, 252: 0.40}, vol_penalty=0.10, trend_window=126, trend_required=True),
}
