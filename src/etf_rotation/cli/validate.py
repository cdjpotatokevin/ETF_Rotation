from __future__ import annotations

import argparse
import json

from etf_rotation.data.pipeline import validate_daily_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ETF rotation data")
    parser.parse_args()
    report = validate_daily_file()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
