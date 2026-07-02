from __future__ import annotations

from datetime import date
from typing import List

import numpy as np
import pandas as pd

from etf_rotation.models import ETFAsset, ETF_DAILY_COLUMNS


class SyntheticMarketDataProvider:
    name = "synthetic"

    def __init__(self, seed: int = 20260630):
        self.seed = seed

    def fetch_etf_daily(
        self,
        assets: List[ETFAsset],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        dates = pd.bdate_range(start=start, end=end)
        frames = []
        for idx, asset in enumerate(assets):
            rng = np.random.default_rng(self.seed + idx)
            drift = 0.00015 + (idx % 5) * 0.00003
            vol = 0.012 + (idx % 4) * 0.002
            returns = rng.normal(drift, vol, size=len(dates))
            close = 1.0 * np.cumprod(1 + returns)
            overnight = rng.normal(0, vol / 3, size=len(dates))
            open_ = close * (1 + overnight)
            high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, vol / 2, size=len(dates))))
            low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, vol / 2, size=len(dates))))
            volume = rng.integers(2_000_000, 80_000_000, size=len(dates))
            amount = volume * close
            turnover = rng.uniform(0.5, 8.0, size=len(dates))
            nav = close * (1 + rng.normal(0, 0.001, size=len(dates)))
            premium_rate = (close / nav - 1) * 100
            shares = rng.integers(300_000_000, 30_000_000_000)
            shares_path = shares + rng.normal(0, shares * 0.002, size=len(dates)).cumsum()

            frame = pd.DataFrame(
                {
                    "date": dates.date,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "bucket": asset.bucket,
                    "theme": asset.theme,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "turnover": turnover,
                    "nav": nav,
                    "premium_rate": premium_rate,
                    "shares_outstanding": np.maximum(shares_path, 1),
                    "source": self.name,
                }
            )
            frames.append(frame)

        result = pd.concat(frames, ignore_index=True)
        return result[ETF_DAILY_COLUMNS]
