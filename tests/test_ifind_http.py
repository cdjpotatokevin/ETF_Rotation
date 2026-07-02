from etf_rotation.config import load_etf_pool
from etf_rotation.data.ifind_http import IFindHttpMarketDataProvider


def test_ifind_http_response_parser():
    asset = load_etf_pool()[0]
    response = {
        "errorcode": 0,
        "errmsg": "",
        "tables": [
            {
                "thscode": asset.symbol,
                "time": ["2026-06-22", "2026-06-23"],
                "table": {
                    "open": [1.5, 1.6],
                    "high": [1.7, 1.8],
                    "low": [1.4, 1.5],
                    "close": [1.6, 1.7],
                    "volume": [1000, 1200],
                    "amount": [1600, 2040],
                    "turnoverRatio": [10.0, 12.0],
                    "netAssetValue": [1.59, 1.69],
                    "premiumRatio": [0.63, 0.59],
                },
            }
        ],
    }
    frame = IFindHttpMarketDataProvider()._response_to_frame(response, {asset.symbol: asset})
    assert len(frame) == 2
    assert frame["source"].iloc[0] == "ifind_http"
    assert frame["shares_outstanding"].iloc[0] == 10000
