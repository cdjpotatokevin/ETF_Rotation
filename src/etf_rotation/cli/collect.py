from __future__ import annotations

import argparse

from etf_rotation.data.pipeline import collect_daily


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect ETF rotation data")
    parser.add_argument("--provider", default="synthetic", choices=["synthetic", "ifind-http"])
    args = parser.parse_args()
    path = collect_daily(provider_name=args.provider)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
