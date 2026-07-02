import pandas as pd

from etf_rotation.backtest.macro_overlay import MacroOverlayConfig, apply_macro_overlay, compute_macro_overlay


def sample_macro():
    rows = []
    values_by_date = {
        "2021-01-31": [52.0, 0.5, 1.0, 10.0, 9.0, 2.8],
        "2021-02-28": [51.0, 0.6, 1.2, 10.2, 9.2, 2.9],
        "2021-03-31": [48.0, 2.0, 4.0, 8.0, 7.0, 3.6],
        "2021-04-30": [47.5, 2.2, 4.5, 7.5, 6.8, 3.8],
    }
    for date, values in values_by_date.items():
        for indicator_id, value in zip(
            ["pmi_mfg", "cpi_yoy", "ppi_yoy", "m2_yoy", "social_financing_yoy", "cn_10y_yield"],
            values,
        ):
            rows.append({"date": date, "indicator_id": indicator_id, "value": value})
    return pd.DataFrame(rows)


def test_compute_macro_overlay_produces_target_exposure():
    dates = pd.date_range("2021-02-01", "2021-05-31", freq="B")
    overlay = compute_macro_overlay(
        sample_macro(),
        dates,
        MacroOverlayConfig(medium_risk_threshold=0.1, high_risk_threshold=0.5, release_lag_days=0),
    )
    assert {"macro_risk_score", "target_exposure"} <= set(overlay.columns)
    assert set(overlay["target_exposure"].unique()) <= {1.0, 0.75, 0.5}
    assert len(overlay) == len(dates)


def test_apply_macro_overlay_moves_scaled_weight_to_cash():
    weights = pd.DataFrame(
        [
            {"date": "2021-03-05", "symbol": "A", "weight": 0.25},
            {"date": "2021-03-05", "symbol": "B", "weight": 0.25},
            {"date": "2021-03-05", "symbol": "CASH", "weight": 0.50},
        ]
    )
    overlay = pd.DataFrame({"date": pd.to_datetime(["2021-03-05"]), "target_exposure": [0.5]})
    adjusted = apply_macro_overlay(weights, overlay)
    by_symbol = adjusted.set_index("symbol")["weight"]
    assert by_symbol["A"] == 0.125
    assert by_symbol["B"] == 0.125
    assert by_symbol["CASH"] == 0.75
    assert adjusted["weight"].sum() == 1.0
