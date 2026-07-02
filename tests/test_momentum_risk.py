import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, build_weekly_weights
from etf_rotation.backtest.risk_control import RiskControlConfig, apply_risk_controls
from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.factors.momentum_variants import MOMENTUM_SPECS, compute_momentum_variant
from scripts.tune_momentum_risk import parse_optional_floats, parse_specs, sanitize_json


def test_momentum_variant_scores_are_bounded():
    cfg = load_project_config()
    assets = load_etf_pool()[:4]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_momentum_variant(daily, MOMENTUM_SPECS["m_3_6_trend"])
    assert scores["momentum_score"].dropna().between(0, 1).all()
    assert {"raw_momentum", "trend_ok"} <= set(scores.columns)


def test_apply_risk_controls_keeps_weights_sum_to_one():
    cfg = load_project_config()
    assets = load_etf_pool()[:4]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_momentum_variant(daily, MOMENTUM_SPECS["m_3_6"])
    scores["baseline_score"] = scores["momentum_score"]
    weights = build_weekly_weights(scores, BacktestConfig(top_n=3, max_single_weight=0.25))
    adjusted = apply_risk_controls(
        daily,
        scores,
        weights,
        BacktestConfig(top_n=3, max_single_weight=0.25),
        RiskControlConfig(target_vol=0.2),
    )
    totals = adjusted.groupby("date")["weight"].sum().round(8)
    assert totals.eq(1.0).all()


def test_tune_momentum_risk_parsers():
    assert parse_specs("m_3_6,m_6_12") == ["m_3_6", "m_6_12"]
    assert parse_optional_floats("none,0.18") == [None, 0.18]


def test_sanitize_json_replaces_nan():
    assert sanitize_json({"x": float("nan")}) == {"x": None}
