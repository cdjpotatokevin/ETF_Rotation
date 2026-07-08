from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etf_rotation.config import resolve_project_path


DISPLAY_COLUMNS = [
    "年度",
    "ETF池",
    "方案",
    "收益",
    "沪深300ETF",
    "超额",
    "最大回撤",
    "Sharpe",
    "信息比率",
    "平均日换手",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a single-year performance display table")
    parser.add_argument("--input", default="data/processed/long_sample_2019/long_sample_walk_forward.csv")
    parser.add_argument("--output-dir", default="data/processed/single_year_performance")
    parser.add_argument("--doc", default="docs/SINGLE_YEAR_PERFORMANCE_RECORD.md")
    parser.add_argument("--include-variants", default="top3_cap25_cash,top3_full_cap33,top4_full_cap25")
    args = parser.parse_args()

    walk = pd.read_csv(resolve_project_path(args.input))
    include = [item.strip() for item in args.include_variants.split(",") if item.strip()]
    table = build_single_year_table(walk, include_variants=include)

    out_dir = resolve_project_path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "single_year_performance.csv", index=False)
    markdown_table = format_markdown_table(table)
    (out_dir / "single_year_performance.md").write_text(markdown_table + "\n", encoding="utf-8")

    doc_path = resolve_project_path(args.doc)
    doc_path.write_text(build_report_doc(table), encoding="utf-8")
    print(markdown_table)


def build_single_year_table(walk: pd.DataFrame, include_variants: list[str] | None = None) -> pd.DataFrame:
    frame = walk.copy()
    if include_variants:
        frame = frame[frame["key"].isin(include_variants)].copy()
    frame["_variant_order"] = frame["key"].map({key: idx for idx, key in enumerate(include_variants or [])}).fillna(999)
    frame["_pool_order"] = frame["pool_name"].map({"原19只ETF池": 0, "扩展A股ETF池": 1}).fillna(999)
    frame["_split_order"] = frame["split"].map(split_sort_key)
    frame = frame.sort_values(["_split_order", "_pool_order", "_variant_order", "pool_name", "variant_name"])
    result = pd.DataFrame(
        {
            "年度": frame["split"].astype(str),
            "ETF池": frame["pool_name"].astype(str),
            "方案": frame["variant_name"].astype(str),
            "收益": frame["test_total_return"].map(format_pct),
            "沪深300ETF": frame["test_benchmark_total_return"].map(format_pct),
            "超额": frame["test_excess_total_return"].map(format_pct),
            "最大回撤": frame["test_max_drawdown"].map(format_pct),
            "Sharpe": frame["test_sharpe"].map(format_number),
            "信息比率": frame["test_information_ratio"].map(format_number),
            "平均日换手": frame["test_avg_turnover"].map(format_pct),
        }
    )
    return result[DISPLAY_COLUMNS].reset_index(drop=True)


def split_sort_key(value: object) -> int:
    text = str(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits[:4]) if digits else 9999


def format_pct(value: float) -> str:
    return f"{float(value) * 100:.2f}%"


def format_number(value: float) -> str:
    return f"{float(value):.2f}"


def format_markdown_table(table: pd.DataFrame) -> str:
    headers = list(table.columns)
    left_aligned = {"年度", "ETF池", "方案"}
    align = ["---" if header in left_aligned else "---:" for header in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(align) + "|",
    ]
    for row in table.itertuples(index=False):
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def build_report_doc(table: pd.DataFrame) -> str:
    main = table[(table["ETF池"] == "原19只ETF池") & (table["方案"] == "Top3 单只25%上限，剩余现金")]
    expanded = table[(table["ETF池"] == "扩展A股ETF池") & (table["方案"] == "Top3 单只25%上限，剩余现金")]
    return "\n".join(
        [
            "# 单年度业绩展示",
            "",
            "日期：2026-07-08",
            "",
            "## 说明",
            "",
            "本表基于 `2019-01-01` 起的长样本 walk-forward 回测结果生成，展示每个单年度或年初至今区间的测试期表现。",
            "",
            "- 基准：`510300.SH` 沪深300ETF",
            "- 数据最新日期：`2026-07-08`",
            "- 最新调仓信号日期：`2026-07-03`",
            "- 交易成本：单边 `5bps`",
            "",
            "## 原19只ETF池主策略",
            "",
            format_markdown_table(main),
            "",
            "## 扩展A股ETF池主策略",
            "",
            format_markdown_table(expanded),
            "",
            "## 全部方案明细",
            "",
            format_markdown_table(table),
            "",
            "## 解读",
            "",
            "- 原 19 只 ETF 池主策略在 2021、2023、2024、2025、2026YTD 为正收益，2022 年为负收益但仍跑赢沪深300ETF。",
            "- 扩展 A 股 ETF 池主策略在各年度表现更均衡，2022 年跌幅小于原池，2025 和 2026YTD 的收益弹性更高。",
            "- Top3 满仓版本在多数上涨年份收益更高，但单年度回撤通常也更深；因此仍更适合作为进攻分支。",
        ]
    ) + "\n"


if __name__ == "__main__":
    main()
