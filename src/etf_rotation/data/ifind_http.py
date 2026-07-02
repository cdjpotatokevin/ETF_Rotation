from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

import pandas as pd

from etf_rotation.models import ETFAsset, ETF_DAILY_COLUMNS


BASE_URL = "https://quantapi.51ifind.com/api/v1"


class IFindHttpError(RuntimeError):
    pass


@dataclass
class IFindHttpClient:
    refresh_token: Optional[str] = None
    base_url: str = BASE_URL
    timeout: int = 30

    def __post_init__(self) -> None:
        if self.refresh_token is None:
            self.refresh_token = os.getenv("IFIND_REFRESH_TOKEN")
        self._access_token: Optional[str] = None

    def get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.refresh_token:
            raise IFindHttpError("IFIND_REFRESH_TOKEN is not configured")

        request = urllib.request.Request(
            f"{self.base_url}/get_access_token",
            data=b"",
            method="POST",
            headers={"refresh_token": self.refresh_token},
        )
        payload = self._open_json(request)
        token = (
            payload.get("access_token")
            or payload.get("data", {}).get("access_token")
            or payload.get("data", {}).get("accessToken")
        )
        if not token:
            raise IFindHttpError(f"access token not found in response keys: {list(payload.keys())}")
        self._access_token = token
        return token

    def post_service(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        access_token = self.get_access_token()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{endpoint}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "access_token": access_token,
            },
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise IFindHttpError(str(exc)) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IFindHttpError(f"invalid JSON response: {raw[:500]}") from exc


class IFindHttpMarketDataProvider:
    name = "ifind_http"

    indicators = (
        "open,high,low,close,volume,amount,turnoverRatio,"
        "netAssetValue,accumulatedNAV,premiumRatio"
    )

    def __init__(self, client: IFindHttpClient | None = None, batch_size: int = 20):
        self.client = client or IFindHttpClient()
        self.batch_size = batch_size

    def fetch_etf_daily(
        self,
        assets: list[ETFAsset],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        frames = []
        symbols = list(asset_by_symbol)
        for batch_start in range(0, len(symbols), self.batch_size):
            batch = symbols[batch_start : batch_start + self.batch_size]
            payload = {
                "codes": ",".join(batch),
                "indicators": self.indicators,
                "startdate": start.isoformat(),
                "enddate": end.isoformat(),
                "functionpara": {"Interval": "D", "Fill": "Blank"},
            }
            response = self.client.post_service("cmd_history_quotation", payload)
            frames.append(self._response_to_frame(response, asset_by_symbol))

        if not frames:
            return pd.DataFrame(columns=ETF_DAILY_COLUMNS)
        result = pd.concat(frames, ignore_index=True)
        return result[ETF_DAILY_COLUMNS]

    def _response_to_frame(
        self,
        response: Dict[str, Any],
        asset_by_symbol: dict[str, ETFAsset],
    ) -> pd.DataFrame:
        if response.get("errorcode") not in (0, "0", None):
            raise IFindHttpError(f"iFinD error {response.get('errorcode')}: {response.get('errmsg')}")

        rows = []
        for table_block in response.get("tables", []):
            symbol = table_block.get("thscode")
            asset = asset_by_symbol.get(symbol)
            if asset is None:
                continue
            dates = table_block.get("time", [])
            values = table_block.get("table", {})
            for idx, day in enumerate(dates):
                row = {
                    "date": day,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "bucket": asset.bucket,
                    "theme": asset.theme,
                    "open": _take(values, "open", idx),
                    "high": _take(values, "high", idx),
                    "low": _take(values, "low", idx),
                    "close": _take(values, "close", idx),
                    "volume": _take(values, "volume", idx),
                    "amount": _take(values, "amount", idx),
                    "turnover": _take(values, "turnoverRatio", idx),
                    "nav": _take(values, "netAssetValue", idx),
                    "premium_rate": _take(values, "premiumRatio", idx),
                    "shares_outstanding": None,
                    "source": self.name,
                }
                if row["nav"] is None:
                    row["nav"] = row["close"]
                row["shares_outstanding"] = _derive_shares(row["volume"], row["turnover"])
                rows.append(row)

        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame(columns=ETF_DAILY_COLUMNS)
        for column in ["open", "high", "low", "close", "volume", "amount", "turnover", "nav", "premium_rate", "shares_outstanding"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["premium_rate"] = frame["premium_rate"].fillna((frame["close"] / frame["nav"] - 1) * 100)
        frame = frame.dropna(subset=["open", "high", "low", "close", "volume", "amount", "turnover"])
        frame["shares_outstanding"] = frame.groupby("symbol")["shares_outstanding"].ffill().bfill()
        return frame[ETF_DAILY_COLUMNS]


def _take(values: Dict[str, Any], key: str, idx: int) -> Any:
    series = values.get(key, [])
    if idx >= len(series):
        return None
    return series[idx]


def _derive_shares(volume: Any, turnover: Any) -> Optional[float]:
    if volume in (None, "") or turnover in (None, "", 0):
        return None
    try:
        turnover_float = float(turnover)
        if turnover_float == 0:
            return None
        return float(volume) / (turnover_float / 100.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
