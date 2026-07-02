from __future__ import annotations

import numpy as np
import pandas as pd


def cross_sectional_rank(frame: pd.DataFrame, column: str, out: str) -> pd.DataFrame:
    ranked = frame.copy()
    ranked[out] = ranked.groupby("date")[column].rank(pct=True)
    return ranked


def cross_sectional_zscore(frame: pd.DataFrame, column: str, out: str) -> pd.DataFrame:
    result = frame.copy()

    def _zscore(series: pd.Series) -> pd.Series:
        std = series.std(ddof=0)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / std

    result[out] = result.groupby("date")[column].transform(_zscore)
    return result


def clip_score(series: pd.Series) -> pd.Series:
    return series.clip(lower=0.0, upper=1.0)
