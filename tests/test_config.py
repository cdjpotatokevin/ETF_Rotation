from etf_rotation.config import load_etf_pool, load_project_config


def test_load_project_config():
    cfg = load_project_config()
    assert cfg.project_name == "ETF Rotation"
    assert cfg.data_start.isoformat() == "2021-01-01"
    assert cfg.data_end.isoformat() == "2026-07-03"


def test_load_etf_pool():
    assets = load_etf_pool()
    assert len(assets) >= 15
    assert len({asset.symbol for asset in assets}) == len(assets)
    assert {"industry", "style"} <= {asset.bucket for asset in assets}
