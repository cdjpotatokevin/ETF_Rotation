from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.validation import validate_etf_daily


def test_synthetic_provider_generates_valid_daily_data():
    cfg = load_project_config()
    assets = load_etf_pool()[:3]
    frame = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_end)
    result = validate_etf_daily(frame, [asset.symbol for asset in assets])
    assert result.ok, result.errors
    assert frame["symbol"].nunique() == 3
    assert frame["date"].min().isoformat() == "2021-01-01"
