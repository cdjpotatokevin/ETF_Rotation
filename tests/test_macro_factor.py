import pandas as pd

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.macro import compute_macro_regime_components, compute_macro_resonance


def sample_macro():
    rows = []
    for date, values in {
        "2021-01-31": [50.0, 0.5, 1.0, 9.0, 8.0, 3.0],
        "2021-02-28": [51.0, 0.8, 1.5, 9.2, 8.2, 3.1],
        "2021-03-31": [49.0, 1.2, 2.0, 8.8, 7.8, 2.9],
        "2021-04-30": [52.0, 1.0, 2.5, 9.5, 8.5, 3.2],
    }.items():
        for indicator_id, value in zip(
            ["pmi_mfg", "cpi_yoy", "ppi_yoy", "m2_yoy", "social_financing_yoy", "cn_10y_yield"],
            values,
        ):
            rows.append({"date": date, "indicator_id": indicator_id, "value": value})
    return pd.DataFrame(rows)


def test_compute_macro_regime_components_aligns_to_daily_dates():
    dates = pd.date_range("2021-02-01", "2021-04-30", freq="B")
    components = compute_macro_regime_components(sample_macro(), dates)
    assert len(components) == len(dates)
    assert {"macro_growth", "macro_inflation", "macro_liquidity", "macro_risk_off"} <= set(components.columns)
    assert components[["macro_growth", "macro_liquidity"]].notna().all().all()


def test_compute_macro_resonance_scores_are_ranked():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_macro_resonance(daily, sample_macro())
    assert {"macro_resonance_score", "macro_raw_score"} <= set(scores.columns)
    assert scores["macro_resonance_score"].dropna().between(0, 1).all()


def test_ic_includes_macro_resonance_score():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_macro_resonance(daily, sample_macro())
    ic = calculate_factor_ic(daily, scores)
    assert "macro_resonance_score" in set(ic["factor"])
