import importlib.util

import pytest

from etf_rotation.config import load_etf_pool, load_project_config
from etf_rotation.data.synthetic import SyntheticMarketDataProvider
from etf_rotation.storage import ParquetStore


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pyarrow") is None,
    reason="pyarrow is required for parquet IO",
)


def test_parquet_store_roundtrip(tmp_path):
    cfg = load_project_config()
    assets = load_etf_pool()[:2]
    frame = SyntheticMarketDataProvider().fetch_etf_daily(assets, cfg.data_start, cfg.data_start)
    store = ParquetStore(tmp_path)
    path = store.write("sample", frame)
    assert path.exists()
    loaded = store.read("sample")
    assert len(loaded) == len(frame)
    assert set(loaded["symbol"]) == {asset.symbol for asset in assets}
