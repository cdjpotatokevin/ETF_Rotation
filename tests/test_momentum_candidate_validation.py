import pandas as pd

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from scripts.validate_momentum_candidate import (
    CandidateConfig,
    DEFAULT_SPLITS,
    apply_liquidity_filter,
    compute_candidate_scores,
    parse_cost_bps,
    parse_optional_float,
    parse_optional_floats,
    parse_strings,
    run_cost_sensitivity,
    run_implementation_sensitivity,
    run_walk_forward,
)


def test_candidate_validation_parsers():
    assert parse_cost_bps("0,5,10") == [0.0, 5.0, 10.0]
    assert parse_optional_float("none") is None
    assert parse_optional_float("0.60") == 0.6
    assert parse_optional_floats("none,100") == [None, 100.0]
    assert parse_strings("W-FRI,M") == ["W-FRI", "M"]


def test_default_walk_forward_splits_are_ordered():
    for _, train_start, train_end, test_start, test_end in DEFAULT_SPLITS:
        assert pd.Timestamp(train_start) <= pd.Timestamp(train_end)
        assert pd.Timestamp(train_end) < pd.Timestamp(test_start)
        assert pd.Timestamp(test_start) <= pd.Timestamp(test_end)


def test_walk_forward_and_cost_sensitivity_return_rows():
    cfg = load_project_config()
    assets = load_etf_pool()[:4]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_candidate_scores(daily, "m_1_3")
    candidate = CandidateConfig(spec="m_1_3", top_n=2, min_score=0.5, transaction_cost_bps=5.0)
    splits = (("one", cfg.data_start, "2023-12-31", "2024-01-01", "2024-12-31"),)

    walk_forward = run_walk_forward(daily, scores, cfg.benchmark_symbol, candidate, splits)
    cost_sensitivity = run_cost_sensitivity(daily, scores, cfg.benchmark_symbol, candidate, [0, 10])
    implementation_sensitivity = run_implementation_sensitivity(daily, scores, cfg.benchmark_symbol, candidate, ["W-FRI", "M"], [None])

    assert len(walk_forward) == 1
    assert {"test_total_return", "test_sharpe"} <= set(walk_forward.columns)
    assert list(cost_sensitivity["transaction_cost_bps"]) == [0.0, 10.0]
    assert list(implementation_sensitivity["rebalance_frequency"]) == ["W-FRI", "M"]


def test_apply_liquidity_filter_excludes_low_amount_rows():
    scores = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "symbol": ["A", "B"],
            "momentum_score": [0.9, 0.8],
            "baseline_score": [0.9, 0.8],
        }
    )
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "symbol": ["A", "B"],
            "amount": [200_000_000.0, 10_000_000.0],
        }
    )
    filtered = apply_liquidity_filter(scores, daily, min_avg_amount=100_000_000.0, window=20)
    by_symbol = filtered.set_index("symbol")["baseline_score"]
    assert by_symbol["A"] == 0.9
    assert by_symbol["B"] == -1.0
