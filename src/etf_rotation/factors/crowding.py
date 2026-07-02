from __future__ import annotations

import pandas as pd

from .common import cross_sectional_rank


def compute_crowding(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.sort_values(["symbol", "date"]).copy()
    grouped = data.groupby("symbol")
    data["turnover_ma_1m"] = grouped["turnover"].rolling(21).mean().reset_index(level=0, drop=True)
    data["amount_ma_1m"] = grouped["amount"].rolling(21).mean().reset_index(level=0, drop=True)
    data["turnover_ma_3m"] = grouped["turnover"].rolling(63).mean().reset_index(level=0, drop=True)
    data["amount_ma_3m"] = grouped["amount"].rolling(63).mean().reset_index(level=0, drop=True)
    data["turnover_heat"] = data["turnover_ma_1m"] / data["turnover_ma_3m"] - 1
    data["amount_heat"] = data["amount_ma_1m"] / data["amount_ma_3m"] - 1
    data["raw_crowding"] = -(0.6 * data["turnover_heat"] + 0.4 * data["amount_heat"])
    ranked = cross_sectional_rank(data, "raw_crowding", "crowding_score")
    return ranked[["date", "symbol", "crowding_score", "turnover_heat", "amount_heat"]]
