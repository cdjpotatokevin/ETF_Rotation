import pandas as pd
import pytest

from etf_rotation.backtest.engine import BacktestConfig, run_weekly_rotation_backtest, select_rebalance_dates
from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.factors.scoring import compute_baseline_scores


def test_run_weekly_rotation_backtest():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_baseline_scores(daily)
    result = run_weekly_rotation_backtest(
        daily=daily,
        scores=scores,
        benchmark_symbol=assets[0].symbol,
        config=BacktestConfig(top_n=3, max_single_weight=0.25),
    )
    assert not result["curve"].empty
    assert not result["weights"].empty
    assert "sharpe" in result["metrics"]
    assert result["weights"].groupby("date")["weight"].sum().round(8).eq(1.0).all()


def test_run_weekly_rotation_backtest_handles_empty_selection_as_cash():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_baseline_scores(daily)
    result = run_weekly_rotation_backtest(
        daily=daily,
        scores=scores,
        benchmark_symbol=assets[0].symbol,
        config=BacktestConfig(top_n=3, min_score=2.0),
    )
    assert not result["curve"].empty
    assert result["weights"].empty
    assert result["metrics"]["total_return"] == 0.0


def test_select_rebalance_dates_supports_monthly_last_trading_day():
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-28", "2024-02-29"])})
    dates = select_rebalance_dates(frame, "M")
    assert list(dates.dt.strftime("%Y-%m-%d")) == ["2024-01-31", "2024-02-29"]


def test_select_rebalance_dates_rejects_unknown_frequency():
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-31"])})
    with pytest.raises(ValueError, match="unsupported rebalance frequency"):
        select_rebalance_dates(frame, "D")
