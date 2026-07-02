from __future__ import annotations

import pandas as pd

from .common import cross_sectional_rank


def compute_momentum(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.sort_values(["symbol", "date"]).copy()
    grouped = data.groupby("symbol")["close"]
    data["ret_1m"] = grouped.pct_change(21)
    data["ret_3m"] = grouped.pct_change(63)
    data["ret_6m"] = grouped.pct_change(126)
    data["vol_3m"] = grouped.pct_change().groupby(data["symbol"]).rolling(63).std().reset_index(level=0, drop=True)
    data["raw_momentum"] = (
        0.35 * data["ret_1m"]
        + 0.40 * data["ret_3m"]
        + 0.25 * data["ret_6m"]
        - 0.20 * data["vol_3m"].fillna(0)
    )
    ranked = cross_sectional_rank(data, "raw_momentum", "momentum_score")
    return ranked[["date", "symbol", "momentum_score", "ret_1m", "ret_3m", "ret_6m", "vol_3m"]]
