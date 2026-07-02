from __future__ import annotations

import argparse
import json

from etf_rotation.backtest.pipeline import run_baseline_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ETF rotation baseline backtest")
    parser.parse_args()
    result = run_baseline_backtest()
    output = {k: str(v) for k, v in result.items() if k.endswith("_path")}
    output["metrics"] = result["metrics"]
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
