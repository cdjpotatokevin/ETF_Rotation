# 仓位分配方案比较记录

日期：2026-07-08

## 目标

回应“Top3 + 单只 25% 上限会导致权益仓位最高只有 75%”的问题，将几种仓位分配方案放到同一套真实 iFinD 数据回测框架中并排比较。

本次只改变组合分配方式，不改变动量信号本身：

- 动量规格：`m_1_3_6`
- 最低得分：`0.60`
- 调仓频率：每周五
- 交易成本：单边 `5bps`
- 基准：`510300.SH` 沪深300ETF
- 数据截至：`2026-07-08`

数据说明：ETF 历史日线已通过 iFinD HTTP 回填并增量刷新至 `2026-07-08`，本地原始行情最早可用日期为 `2019-01-02`。本记录仍按主策略配置窗口 `2021-01-01` 至 `2026-07-08` 回测；2019 起的长样本结果单独记录在 `docs/LONG_SAMPLE_2019_BACKTEST_RECORD.md`。

## 比较方案

| 方案键 | 说明 | Top N | 单只上限 | 理论权益仓位上限 |
|---|---|---:|---:|---:|
| `top3_cap25_cash` | Top3 单只 25% 上限，剩余现金 | 3 | 25.00% | 75% |
| `top3_full_cap33` | Top3 满仓集中，单只 33.33% | 3 | 33.33% | 100% |
| `top4_full_cap25` | Top4 满仓分散，单只 25% | 4 | 25.00% | 100% |

## 输出文件

- `data/processed/allocation_variant_comparison/allocation_variant_metrics.parquet`
- `data/processed/allocation_variant_comparison/allocation_variant_metrics.csv`
- `data/processed/allocation_variant_comparison/latest_allocation_weights.parquet`
- `data/processed/allocation_variant_comparison/latest_allocation_weights.csv`
- `data/processed/allocation_variant_comparison/allocation_variant_walk_forward.parquet`
- `data/processed/allocation_variant_comparison/allocation_variant_walk_forward.csv`
- `data/processed/allocation_variant_comparison/summary.json`

## 全样本结果

| 方案 | 总收益 | 年化收益 | 年化波动 | Sharpe | 最大回撤 | 超额收益 | 信息比率 | 平均换手 | 最新权益仓位 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Top3 单只25%上限，剩余现金 | 94.02% | 13.34% | 20.06% | 0.66 | -19.04% | 104.07% | 0.96 | 6.65% | 75% |
| Top3 满仓集中，单只33.33% | 130.85% | 17.12% | 26.75% | 0.64 | -25.22% | 140.90% | 1.00 | 8.87% | 100% |
| Top4 满仓分散，单只25% | 93.89% | 13.32% | 25.23% | 0.53 | -32.81% | 103.93% | 0.90 | 7.61% | 100% |

## 最新持仓

最新调仓日：`2026-07-03`。

### Top3 单只25%上限，剩余现金

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

### Top3 满仓集中，单只33.33%

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 33.33% |
| `515000.SH` | 科技ETF | 33.33% |
| `159915.SZ` | 创业板ETF | 33.33% |

### Top4 满仓分散，单只25%

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `159949.SZ` | 创业板50ETF | 25% |

## 样本外结果

| 方案 | 2022收益 | 2022回撤 | 2023收益 | 2024收益 | 2025收益 | 2026H1收益 |
|---|---:|---:|---:|---:|---:|---:|
| Top3 单只25%上限，剩余现金 | -7.58% | -13.99% | 0.55% | 25.53% | 27.84% | 30.40% |
| Top3 满仓集中，单只33.33% | -10.61% | -18.37% | 0.33% | 33.69% | 37.49% | 41.42% |
| Top4 满仓分散，单只25% | -18.63% | -21.70% | -1.24% | 31.45% | 41.58% | 34.71% |

## 解读

结论比较清楚：

- 当前 `Top3 + 25%上限 + 现金` 不是 bug，而是一个保守仓位设计。它牺牲一部分上涨弹性，换来更低波动和更小回撤。
- `Top3 满仓集中` 的绝对收益最高，信息比率也略高，但最大回撤从 `-19.04%` 放大到 `-25.22%`，年化波动从 `20.06%` 提高到 `26.75%`。它适合作为进攻分支，而不是无条件替代主策略。
- `Top4 满仓分散` 没有达到预期。加入第 4 名后虽然满仓，但信号质量下降，收益几乎没有超过当前版，最大回撤扩大到 `-32.81%`，弱于 Top3 满仓版。

## 建议

暂时不把 Top4 满仓分散版纳入主策略。

后续保留两条可监控分支：

- 稳健主分支：`top3_cap25_cash`
- 进攻备选分支：`top3_full_cap33`

实盘或模拟盘可以根据风险预算选择：

- 如果优先控制回撤和波动，继续使用当前 75% 权益仓位上限。
- 如果接受约 25% 历史最大回撤和更高波动，可以考虑 Top3 满仓集中版。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/compare_allocation_variants.py
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- 仓位方案比较完成
- 单元测试：61 个通过
