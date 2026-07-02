from scripts.tune_factor_weights import apply_weights, key_for, weight_grid


def test_weight_grid_sums_to_one():
    grid = weight_grid(0.5)
    assert len(grid) == 6
    assert all(abs(sum(row.values()) - 1.0) < 1e-9 for row in grid)


def test_key_for_weights():
    key = key_for({"momentum_score": 0.2, "fund_flow_score": 0.3, "crowding_score": 0.5})
    assert key == "m0.2_f0.3_c0.5"
