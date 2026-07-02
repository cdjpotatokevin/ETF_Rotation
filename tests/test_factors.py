from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.factors.ic import calculate_factor_ic
from etf_rotation.factors.scoring import compute_baseline_scores


def test_compute_baseline_scores():
    cfg = load_project_config()
    assets = load_etf_pool()[:4]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_baseline_scores(daily)
    assert {"momentum_score", "fund_flow_score", "crowding_score", "baseline_score"} <= set(scores.columns)
    assert scores["baseline_score"].between(0, 1).all()
    assert scores["symbol"].nunique() == 4


def test_calculate_factor_ic():
    cfg = load_project_config()
    assets = load_etf_pool()[:4]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_baseline_scores(daily)
    ic = calculate_factor_ic(daily, scores)
    assert {"factor", "mean_ic", "ic_ir", "positive_ratio", "observations"} <= set(ic.columns)
    assert len(ic) == 4
