from __future__ import annotations

from datetime import date
from typing import List, Protocol

import pandas as pd

from etf_rotation.models import ETFAsset


class MarketDataProvider(Protocol):
    name: str

    def fetch_etf_daily(
        self,
        assets: List[ETFAsset],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """Return normalized ETF daily bars for the requested asset pool."""
