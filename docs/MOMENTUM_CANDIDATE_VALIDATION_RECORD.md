# 动量候选策略验证记录

日期：2026-07-01

## 目标

固定动量与风险控制调参阶段选出的候选，不再重新调参，进行独立验证：

- 动量规格：`m_1_3_6`
- 选券：Top 3
- 最低得分：`0.60`
- 单只 ETF 上限：`25%`
- 调仓：每周五
- 交易成本：`5bps`
- 流动性过滤：主分支不使用；另行测试 20 日平均成交额门槛
- 基准：`510300.SH` 沪深300ETF

## 已实现组件

新增代码：

- `scripts/validate_momentum_candidate.py`
- `tests/test_momentum_candidate_validation.py`

回测引擎改进：

- `build_weekly_weights` 在没有 ETF 通过得分门槛时，会返回稳定的空表结构。这样高门槛策略可以自然保持现金，而不是报错。

## 命令

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/validate_momentum_candidate.py
```

输出：

- `data/processed/momentum_candidate_validation/walk_forward.parquet`
- `data/processed/momentum_candidate_validation/walk_forward.csv`
- `data/processed/momentum_candidate_validation/cost_sensitivity.parquet`
- `data/processed/momentum_candidate_validation/cost_sensitivity.csv`
- `data/processed/momentum_candidate_validation/implementation_sensitivity.parquet`
- `data/processed/momentum_candidate_validation/implementation_sensitivity.csv`
- `data/processed/momentum_candidate_validation/candidate_full_curve.parquet`
- `data/processed/momentum_candidate_validation/candidate_full_weights.parquet`
- `data/processed/momentum_candidate_validation/summary.json`

## 最新组合

当前真实 iFinD ETF 数据最新日期为 `2026-07-03`。候选策略最近一次周五调仓日为 `2026-07-03`：

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

数据说明：`2026-07-01` 至 `2026-07-03` 的 ETF 收盘价和成交额通过 iFinD MCP `fund.get_fund_market_performance` 补入；此前历史数据仍来自 iFinD HTTP `cmd_history_quotation`。

## 全样本结果

| 指标 | 数值 |
|---|---:|
| 总收益 | 80.09% |
| 年化收益 | 12.99% |
| 年化波动 | 19.60% |
| Sharpe | 0.66 |
| 最大回撤 | -17.02% |
| 基准总收益 | -7.23% |
| 超额总收益 | 87.32% |
| 信息比率 | 1.06 |
| 平均日换手 | 5.91% |

## 滚动样本外结果

各行参数均固定不变。训练窗口仅作为背景记录，每一行测试期都是训练期之后的下一段区间。

| 测试期 | 测试收益 | 相对基准超额 | Sharpe | 最大回撤 | 信息比率 |
|---|---:|---:|---:|---:|---:|
| 2022 | -12.77% | 8.31% | -0.76 | -14.48% | 0.68 |
| 2023 | 0.05% | 11.44% | 0.00 | -11.77% | 1.24 |
| 2024 | 29.85% | 13.37% | 1.26 | -13.95% | 1.00 |
| 2025 | 27.33% | 5.74% | 1.39 | -14.05% | 0.52 |
| 2026H1 | 30.40% | 26.78% | 2.95 | -13.47% | 2.84 |

解读：

- 候选策略不是单纯依赖 2025-2026 的结果；每个年度/半年度样本外窗口都有正超额。
- 2022 年绝对收益较弱，但相对基准亏损明显更小。
- 2023 年绝对收益接近持平，但仍有明显相对超额。
- 各测试窗口最大回撤大致落在 11.8%-14.5% 区间。

## 交易成本敏感性

| 成本 | 总收益 | 年化收益 | Sharpe | 最大回撤 | 超额收益 |
|---:|---:|---:|---:|---:|---:|
| 0bps | 101.16% | 15.65% | 0.81 | -16.85% | 105.67% |
| 5bps | 94.08% | 14.80% | 0.76 | -17.02% | 98.59% |
| 10bps | 87.25% | 13.94% | 0.72 | -17.19% | 91.76% |
| 20bps | 74.30% | 12.26% | 0.63 | -18.76% | 78.81% |
| 50bps | 40.53% | 7.34% | 0.38 | -27.67% | 45.04% |

解读：

- 策略对中等交易成本具备一定稳健性。即使成本为 20bps，全样本总收益仍为 74.30%，超额收益为 78.81%。
- 成本达到 50bps 时优势明显压缩，实盘应避免高换手执行，并加入真实 ETF 流动性约束。

## 调仓频率与流动性敏感性

流动性过滤使用 20 日平均成交额。主分支为每周五调仓且不加流动性过滤。

| 调仓 | 最低平均成交额 | 总收益 | Sharpe | 最大回撤 | 超额收益 | 平均换手 |
|---|---:|---:|---:|---:|---:|---:|
| 每周 | 无 | 94.08% | 0.76 | -17.02% | 98.59% | 5.92% |
| 每周 | 5000万 | 82.92% | 0.65 | -18.98% | 87.43% | 6.17% |
| 每周 | 1亿 | 67.97% | 0.56 | -26.06% | 72.48% | 5.80% |
| 每周 | 2亿 | 55.45% | 0.48 | -28.55% | 59.95% | 5.59% |
| 每月 | 无 | 40.85% | 0.36 | -21.36% | 45.36% | 3.24% |
| 每月 | 5000万 | 17.15% | 0.16 | -35.52% | 21.66% | 2.99% |
| 每月 | 1亿 | 4.62% | 0.04 | -40.97% | 9.13% | 3.03% |
| 每月 | 2亿 | 76.59% | 0.43 | -36.25% | 81.10% | 2.70% |

解读：

- 当前仍建议以每周调仓作为主分支。月度调仓能降低换手，但在当前动量信号下绩效牺牲过大。
- 如果优先考虑执行纪律，可以把 20 日平均成交额 5000 万作为第一层约束候选。
- 1 亿和 2 亿的周度过滤在当前 19 只 ETF 池中会明显削弱策略优势。
- 月度叠加高流动性门槛不稳定：2 亿门槛行总收益恢复，但回撤更差、风险调整收益更低。

## 建议

保留 `m_1_3_6_top3_min0p6` 作为主研究分支。下一步实用验证包括：

- 继续使用每周调仓。
- 将 20 日平均成交额 5000 万作为第一层实盘执行约束候选，但暂不作为研究基线。
- 将防守分支 `m_3_6_trend_top3_min0p6` 纳入同一验证脚本并行监控。
- 估值、景气和宏观过滤器要等 iFinD 数据源稳定接入后再加入。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/validate_momentum_candidate.py
```

结果：

- 单元测试：25 个通过
- 候选验证已基于真实 iFinD ETF 历史数据完成
