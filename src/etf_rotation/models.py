from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ETFAsset:
    symbol: str
    name: str
    bucket: str
    theme: str
    notes: str = ""


@dataclass(frozen=True)
class ProjectConfig:
    project_name: str
    data_start: date
    data_end: date
    rebalance_frequency: str
    benchmark_symbol: str
    raw_dir: str
    processed_dir: str
    factor_dir: str
    ifind_cli_script: Optional[str]


ETF_DAILY_COLUMNS = [
    "date",
    "symbol",
    "name",
    "bucket",
    "theme",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turnover",
    "nav",
    "premium_rate",
    "shares_outstanding",
    "source",
]
