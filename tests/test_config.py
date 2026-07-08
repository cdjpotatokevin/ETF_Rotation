from pathlib import Path

from etf_rotation.config import load_etf_pool, load_project_config


def test_load_project_config():
    cfg = load_project_config()
    assert cfg.project_name == "ETF Rotation"
    assert cfg.data_start.isoformat() == "2021-01-01"
    assert cfg.data_end.isoformat() == "2026-07-08"


def test_load_etf_pool():
    assets = load_etf_pool()
    assert len(assets) >= 15
    assert len({asset.symbol for asset in assets}) == len(assets)
    assert {"industry", "style"} <= {asset.bucket for asset in assets}


def test_load_expanded_a_share_pool_keeps_default_pool_unchanged():
    base_assets = load_etf_pool()
    expanded_assets = load_etf_pool(Path("config/etf_pool_expanded_a_share.json"))
    base_symbols = {asset.symbol for asset in base_assets}
    expanded_symbols = {asset.symbol for asset in expanded_assets}

    assert len(base_assets) == 19
    assert len(expanded_assets) == 29
    assert base_symbols < expanded_symbols
    assert {"513180.SH", "513050.SH", "513100.SH", "518880.SH", "511010.SH"}.isdisjoint(expanded_symbols)
    assert {
        "588000.SH",
        "512800.SH",
        "512690.SH",
        "515030.SH",
        "515790.SH",
        "159819.SZ",
        "512980.SH",
        "516020.SH",
        "159611.SZ",
        "159865.SZ",
    } <= expanded_symbols
