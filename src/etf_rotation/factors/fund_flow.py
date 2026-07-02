from __future__ import annotations

import pandas as pd

from .common import cross_sectional_rank


def compute_fund_flow(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.sort_values(["symbol", "date"]).copy()
    grouped = data.groupby("symbol")["shares_outstanding"]
    data["share_chg_1m"] = grouped.pct_change(21)
    data["share_chg_3m"] = grouped.pct_change(63)
    data["raw_fund_flow"] = 0.6 * data["share_chg_1m"] + 0.4 * data["share_chg_3m"]
    ranked = cross_sectional_rank(data, "raw_fund_flow", "fund_flow_score")
    return ranked[["date", "symbol", "fund_flow_score", "share_chg_1m", "share_chg_3m"]]
