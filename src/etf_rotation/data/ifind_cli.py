from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from etf_rotation.models import ETFAsset


DEFAULT_IFIND_SCRIPT = "/Users/sweethome/.codex/skills/ifind-finance-data/scripts/ifind.js"


class IFindCliError(RuntimeError):
    pass


class IFindCliClient:
    def __init__(self, node_bin: str = "node", script_path: str | None = None):
        self.node_bin = node_bin
        self.script_path = script_path or os.getenv("IFIND_CLI_SCRIPT") or DEFAULT_IFIND_SCRIPT

    def call(self, service: str, tool: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        script = Path(self.script_path)
        if not script.exists():
            raise IFindCliError(f"iFind CLI script not found: {script}")
        cmd = [self.node_bin, str(script), service, tool, json.dumps(payload, ensure_ascii=False)]
        completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
        if completed.returncode != 0:
            raise IFindCliError(completed.stderr.strip() or completed.stdout.strip())
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise IFindCliError(f"invalid JSON from iFind CLI: {completed.stdout[:500]}") from exc
        if result.get("ok") is False:
            raise IFindCliError(str(result))
        return result


class IFindCliMarketDataProvider:
    name = "ifind_cli"

    def __init__(self, client: IFindCliClient | None = None):
        self.client = client or IFindCliClient()

    def fetch_etf_daily(
        self,
        assets: List[ETFAsset],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        raise NotImplementedError(
            "The iFind CLI returns natural-language responses and needs a "
            "project-specific parser after live samples are collected. Use "
            "the HTTP provider for batch historical bars or synthetic for tests."
        )

    def fetch_fund_market_text(self, asset: ETFAsset, start: date, end: date) -> Dict[str, Any]:
        query = (
            f"{asset.name}({asset.symbol})在{start.isoformat()}至{end.isoformat()}的"
            "收盘价、成交量、成交额、换手率、单位净值、折溢价率、场内流通份额"
        )
        return self.client.call("fund", "get_fund_market_performance", {"query": query})
