import pandas as pd

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from scripts.compare_allocation_variants import (
    AllocationVariant,
    latest_equity_exposure,
    latest_weight_rows,
    to_candidate_config,
    variant_metadata,
)
from scripts.validate_momentum_candidate import compute_candidate_scores, run_candidate


def test_to_candidate_config_maps_allocation_fields():
    variant = AllocationVariant(key="demo", name="demo", top_n=3, max_single_weight=1 / 3)
    candidate = to_candidate_config(variant)
    assert candidate.top_n == 3
    assert candidate.max_single_weight == 1 / 3
    assert candidate.min_score == 0.60
    assert variant_metadata(variant)["variant_name"] == "demo"


def test_latest_equity_exposure_excludes_cash():
    weights = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-09", "2026-01-09"]),
            "symbol": ["A", "CASH", "A", "CASH"],
            "weight": [0.5, 0.5, 0.75, 0.25],
        }
    )
    assert latest_equity_exposure(weights) == 0.75


def test_allocation_variant_changes_exposure_on_synthetic_data():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    scores = compute_candidate_scores(daily, "m_1_3")
    cash_variant = AllocationVariant(key="cash", name="cash", top_n=3, max_single_weight=0.25, spec="m_1_3")
    full_variant = AllocationVariant(key="full", name="full", top_n=3, max_single_weight=1 / 3, spec="m_1_3")

    cash_result = run_candidate(daily, scores, assets[0].symbol, to_candidate_config(cash_variant))
    full_result = run_candidate(daily, scores, assets[0].symbol, to_candidate_config(full_variant))

    assert latest_equity_exposure(cash_result["weights"]) <= 0.75
    assert latest_equity_exposure(full_result["weights"]) > latest_equity_exposure(cash_result["weights"])
    latest_rows = latest_weight_rows(full_result["weights"], full_variant, daily)
    assert latest_rows
    assert {"variant_name", "asset_name"} <= set(latest_rows[0])
