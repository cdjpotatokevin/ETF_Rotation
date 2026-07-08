import pandas as pd

from scripts.report_single_year_performance import build_single_year_table, format_markdown_table


def test_build_single_year_table_keeps_display_columns_and_pct_values():
    walk = pd.DataFrame(
        {
            "split": ["2024"],
            "pool_name": ["原19只ETF池"],
            "key": ["top3_cap25_cash"],
            "variant_name": ["Top3 单只25%上限，剩余现金"],
            "test_total_return": [0.1234],
            "test_benchmark_total_return": [0.0234],
            "test_excess_total_return": [0.10],
            "test_max_drawdown": [-0.0567],
            "test_sharpe": [1.2345],
            "test_information_ratio": [0.9876],
            "test_avg_turnover": [0.0123],
        }
    )

    table = build_single_year_table(walk)

    assert table.to_dict(orient="records") == [
        {
            "年度": "2024",
            "ETF池": "原19只ETF池",
            "方案": "Top3 单只25%上限，剩余现金",
            "收益": "12.34%",
            "沪深300ETF": "2.34%",
            "超额": "10.00%",
            "最大回撤": "-5.67%",
            "Sharpe": "1.23",
            "信息比率": "0.99",
            "平均日换手": "1.23%",
        }
    ]


def test_format_markdown_table_outputs_pipe_table():
    table = pd.DataFrame({"年度": ["2024"], "收益": ["12.34%"]})

    markdown = format_markdown_table(table)

    assert markdown == "| 年度 | 收益 |\n|---|---:|\n| 2024 | 12.34% |"
