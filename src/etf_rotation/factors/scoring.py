from __future__ import annotations

import pandas as pd

from etf_rotation.factors.crowding import compute_crowding
from etf_rotation.factors.fund_flow import compute_fund_flow
from etf_rotation.factors.momentum import compute_momentum


BASELINE_WEIGHTS = {
    "momentum_score": 0.50,
    "fund_flow_score": 0.25,
    "crowding_score": 0.25,
}


def compute_baseline_scores(daily: pd.DataFrame) -> pd.DataFrame:
    momentum = compute_momentum(daily)
    flow = compute_fund_flow(daily)
    crowding = compute_crowding(daily)
    scores = momentum.merge(flow, on=["date", "symbol"], how="outer")
    scores = scores.merge(crowding, on=["date", "symbol"], how="outer")
    for column in BASELINE_WEIGHTS:
        scores[column] = scores[column].fillna(0.5)
    scores["baseline_score"] = sum(scores[col] * weight for col, weight in BASELINE_WEIGHTS.items())
    return scores.sort_values(["date", "baseline_score"], ascending=[True, False])
