import numpy as np
import pandas as pd

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.ml import BASE_FEATURES, build_ml_feature_frame, fit_logistic, fit_ridge, make_prediction_scores


def test_build_ml_feature_frame_contains_targets_and_features():
    cfg = load_project_config()
    assets = load_etf_pool()[:6]
    daily = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    frame = build_ml_feature_frame(daily, assets[0].symbol, horizon=21)

    assert {"date", "symbol", "forward_return", "target_top"} <= set(frame.columns)
    assert set(BASE_FEATURES) <= set(frame.columns)
    assert frame["symbol"].nunique() == len(assets)
    assert frame["forward_return"].notna().any()


def test_ridge_and_logistic_models_predict_scores():
    train = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"] * 4),
            "symbol": ["A", "B", "C", "D"],
            "ret_5d": [0.01, 0.02, -0.01, 0.03],
            "ret_21d": [0.02, 0.01, -0.02, 0.04],
            "forward_return": [0.03, 0.02, -0.01, 0.05],
            "target_top": [1.0, 0.0, 0.0, 1.0],
        }
    )
    for column in BASE_FEATURES:
        if column not in train:
            train[column] = 0.0
    test = train.copy()
    test["date"] = pd.Timestamp("2024-01-08")

    ridge = fit_ridge(train, BASE_FEATURES, alpha=1.0)
    logistic = fit_logistic(train, BASE_FEATURES, alpha=1.0, iterations=20)
    predictions = test[["date", "symbol"]].copy()
    predictions["prediction"] = ridge.predict(test) + logistic.predict_proba(test)
    scores = make_prediction_scores(predictions)

    assert np.isfinite(predictions["prediction"]).all()
    assert scores["baseline_score"].between(0, 1).all()
