import pandas as pd

from etf_rotation.backtest.engine import BacktestConfig, build_weekly_weights
from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.ml_overlay import (
    MLRegimeOverlayConfig,
    build_ml_regime_weights,
    build_regime_decision_frame,
    selected_basket_return,
)
from scripts.evaluate_ml_regime_overlay import aggregate_thresholds
from scripts.evaluate_ml_regime_overlay import latest_signal as base_latest_signal
from scripts.validate_momentum_candidate import compute_candidate_scores


def test_selected_basket_return_uses_average_selected_return():
    prices = pd.DataFrame(
        {
            "A": [1.0, 1.1],
            "B": [2.0, 1.8],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-08"]),
    )
    value = selected_basket_return(prices, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-08"), ["A", "B"])
    assert round(value, 6) == 0.0


def test_build_regime_decision_frame_has_targets():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_candidate_scores(daily, "m_1_3")
    decisions = build_regime_decision_frame(daily, scores, assets[0].symbol)
    assert {"date", "target_full", "avg_score", "benchmark_ret_21d"} <= set(decisions.columns)
    assert decisions["target_full"].notna().any()


def test_build_ml_regime_weights_switches_between_defensive_and_full():
    scores = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05"] * 3 + ["2024-01-12"] * 3),
            "symbol": ["A", "B", "C", "A", "B", "C"],
            "baseline_score": [1.0, 0.9, 0.8, 1.0, 0.9, 0.8],
        }
    )
    probabilities = pd.DataFrame({"date": pd.to_datetime(["2024-01-05", "2024-01-12"]), "prob_full": [0.4, 0.8]})
    weights = build_ml_regime_weights(scores, probabilities, MLRegimeOverlayConfig(probability_threshold=0.55))
    first = weights[weights["date"] == pd.Timestamp("2024-01-05")]
    second = weights[weights["date"] == pd.Timestamp("2024-01-12")]
    assert first[first["symbol"] != "CASH"]["weight"].iloc[0] == 0.25
    assert round(second[second["symbol"] != "CASH"]["weight"].iloc[0], 6) == round(1 / 3, 6)


def test_aggregate_thresholds_includes_baseline_comparison_columns():
    walk = pd.DataFrame(
        {
            "threshold": [0.5, 0.5],
            "ml_total_return": [0.1, 0.2],
            "ml_sharpe": [1.0, 2.0],
            "ml_max_drawdown": [-0.1, -0.2],
            "ml_excess_total_return": [0.1, 0.2],
            "ml_information_ratio": [0.8, 1.0],
            "defensive_total_return": [0.05, 0.1],
            "defensive_sharpe": [0.5, 0.7],
            "defensive_max_drawdown": [-0.08, -0.1],
            "defensive_information_ratio": [0.4, 0.5],
            "full_total_return": [0.2, 0.3],
            "full_sharpe": [1.5, 2.5],
            "full_max_drawdown": [-0.15, -0.25],
            "full_information_ratio": [1.1, 1.3],
            "full_signal_ratio": [0.2, 0.4],
        }
    )
    result = aggregate_thresholds(walk)
    assert {"avg_defensive_sharpe", "avg_full_sharpe", "worst_full_drawdown"} <= set(result.columns)


def test_latest_signal_uses_last_rebalance_date_when_latest_data_is_not_rebalance_day():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_candidate_scores(daily, "m_1_3")
    decisions = build_regime_decision_frame(daily, scores, assets[0].symbol)

    result = base_latest_signal(daily, scores, decisions, assets[0].symbol, 0.50)

    assert not result["probabilities"].empty
    assert result["probabilities"]["date"].max() <= pd.to_datetime(daily["date"]).max()
