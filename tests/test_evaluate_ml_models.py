import pandas as pd

from scripts.evaluate_ml_models import aggregate_walk_forward, filter_dates, spearman_without_scipy


def test_filter_dates_is_inclusive():
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]), "value": [1, 2, 3]})
    result = filter_dates(frame, "2024-01-02", "2024-01-03")
    assert list(result["value"]) == [2, 3]


def test_aggregate_walk_forward_counts_positive_periods():
    walk = pd.DataFrame(
        {
            "model": ["a", "a", "b"],
            "model_name": ["A", "A", "B"],
            "total_return": [0.1, -0.2, 0.3],
            "sharpe": [1.0, -1.0, 2.0],
            "max_drawdown": [-0.1, -0.3, -0.2],
            "excess_total_return": [0.2, -0.1, 0.4],
            "information_ratio": [0.5, -0.2, 0.8],
            "mean_rank_ic": [0.1, -0.1, 0.2],
        }
    )
    result = aggregate_walk_forward(walk)
    by_model = result.set_index("model")
    assert by_model.loc["a", "positive_periods"] == 1
    assert by_model.loc["a", "worst_drawdown"] == -0.3


def test_spearman_without_scipy_matches_rank_direction():
    frame = pd.DataFrame({"baseline_score": [1.0, 2.0, 3.0], "forward_return": [0.1, 0.2, 0.3]})
    assert spearman_without_scipy(frame) == 1.0
