from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import resolve_project_path


class ParquetStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = resolve_project_path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        suffix = "" if name.endswith(".parquet") else ".parquet"
        return self.base_dir / f"{name}{suffix}"

    def write(self, name: str, frame: pd.DataFrame) -> Path:
        path = self.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        return path

    def read(self, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.path(name))

    def exists(self, name: str) -> bool:
        return self.path(name).exists()
