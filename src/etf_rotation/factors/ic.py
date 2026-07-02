from __future__ import annotations

import pandas as pd


FACTOR_COLUMNS = ["momentum_score", "fund_flow_score", "crowding_score", "baseline_score"]


def calculate_factor_ic(
    daily: pd.DataFrame,
    scores: pd.DataFrame,
    forward_days: int = 21,
) -> pd.DataFrame:
    prices = daily[["date", "symbol", "close"]].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values(["symbol", "date"])
    prices["forward_return"] = prices.groupby("symbol")["close"].shift(-forward_days) / prices["close"] - 1

    factors = scores.copy()
    factors["date"] = pd.to_datetime(factors["date"])
    merged = factors.merge(prices[["date", "symbol", "forward_return"]], on=["date", "symbol"], how="inner")
    rows = []
    available_factors = [factor for factor in FACTOR_COLUMNS if factor in merged.columns]
    for factor in available_factors:
        ic_by_date = merged.groupby("date").apply(
            lambda x: _spearman_without_scipy(x[factor], x["forward_return"]),
            include_groups=False,
        ).dropna()
        if ic_by_date.empty:
            rows.append({"factor": factor, "mean_ic": 0.0, "ic_ir": 0.0, "positive_ratio": 0.0, "observations": 0})
            continue
        std = ic_by_date.std(ddof=0)
        rows.append(
            {
                "factor": factor,
                "mean_ic": float(ic_by_date.mean()),
                "ic_ir": float(ic_by_date.mean() / std) if std else 0.0,
                "positive_ratio": float((ic_by_date > 0).mean()),
                "observations": int(len(ic_by_date)),
            }
        )
    return pd.DataFrame(rows)


def _spearman_without_scipy(left: pd.Series, right: pd.Series) -> float:
    pair = pd.concat([left, right], axis=1).dropna()
    if len(pair) < 2:
        return float("nan")
    ranked = pair.rank(method="average")
    if ranked.iloc[:, 0].std(ddof=0) == 0 or ranked.iloc[:, 1].std(ddof=0) == 0:
        return float("nan")
    return float(ranked.iloc[:, 0].corr(ranked.iloc[:, 1]))
