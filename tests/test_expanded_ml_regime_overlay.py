from pathlib import Path

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from scripts.evaluate_expanded_ml_regime_overlay import evaluate_ml_overlay_for_pool


def test_evaluate_ml_overlay_for_pool_returns_summary_and_named_latest_weights(tmp_path):
    cfg = load_project_config()
    assets = load_etf_pool(Path("config/etf_pool_expanded_a_share.json"))[:8]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)

    result = evaluate_ml_overlay_for_pool(daily, assets[0].symbol, [0.50], tmp_path)

    assert not result["aggregate"].empty
    assert {"threshold", "avg_ml_sharpe", "worst_ml_drawdown"} <= set(result["aggregate"].columns)
    assert not result["latest_weights"].empty
    assert {"symbol", "asset_name", "weight", "prob_full"} <= set(result["latest_weights"].columns)
