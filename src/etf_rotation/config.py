from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from .models import ETFAsset, ProjectConfig


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_project_config(path: Path | None = None) -> ProjectConfig:
    cfg_path = path or ROOT / "config" / "project.json"
    raw = _read_json(cfg_path)
    storage = raw["storage"]
    providers = raw.get("providers", {})
    return ProjectConfig(
        project_name=raw["project_name"],
        data_start=date.fromisoformat(raw["data_start"]),
        data_end=date.fromisoformat(raw["data_end"]),
        rebalance_frequency=raw["rebalance_frequency"],
        benchmark_symbol=raw.get("benchmark_symbol", "510300.SH"),
        raw_dir=storage["raw_dir"],
        processed_dir=storage["processed_dir"],
        factor_dir=storage["factor_dir"],
        ifind_cli_script=providers.get("ifind_cli_script"),
    )


def load_etf_pool(path: Path | None = None) -> List[ETFAsset]:
    pool_path = path or ROOT / "config" / "etf_pool.json"
    raw = _read_json(pool_path)
    assets = [ETFAsset(**item) for item in raw["assets"]]
    symbols = [asset.symbol for asset in assets]
    if len(symbols) != len(set(symbols)):
        raise ValueError("ETF pool contains duplicate symbols")
    return assets


def resolve_project_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
