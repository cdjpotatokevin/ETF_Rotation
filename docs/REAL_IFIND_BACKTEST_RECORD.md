# 真实 iFinD 回测记录

日期：2026-06-30

## 用户决策

基准已确认使用 `510300.SH` 沪深300ETF。

## 真实数据采集

来源：

- iFinD HTTP API
- 接口：`cmd_history_quotation`
- 数据源实现：`src/etf_rotation/data/ifind_http.py`
- 存储文件：`data/raw/etf_daily.parquet`

请求区间：

- `2021-01-01` 至 `2026-06-30`

实际返回区间：

- `2021-06-30` 至 `2026-06-30`

覆盖情况：

- 行数：22,855
- 标的数量：19
- 数据源标签：`ifind_http`
- 大多数 ETF 有 1,211 条观测。
- `159768.SZ` 因可用历史较晚，从 `2022-02-16` 开始。

采集字段：

- 开盘价、最高价、最低价、收盘价
- 成交量、成交额、换手率
- 净值
- 溢价率

MCP 状态更新：

- iFinD MCP 授权已在本地 `~/.config/ifind/mcp_config.json` 配置。
- 官方近期 ETF 份额变化数据已提取到 `data/raw/etf_mcp_share_changes_recent.parquet`。
- MCP 输出当前覆盖 19 只 ETF、156 行，窗口为 `2026-06-22` 至 `2026-06-30`。
- 可用的官方资金流字段为 `exchange_share_change`（当期场内流通份额变化）。
- MCP 官方份额变化与 HTTP 推导份额变化有 114 条有效重叠比较，相关系数为 1.0。
- 验证随后扩展到 2022 至 2026 年五个年度六月窗口；扩展样本包含 782 条 MCP 记录和 554 条有效 HTTP/MCP 比较，整体相关系数为 0.9994。

当前限制：

- HTTP 历史行情接口不直接返回官方每日 ETF 总份额。
- 全区间回测仍使用 `volume / (turnoverRatio / 100)` 推导 `shares_outstanding`。
- MCP 验证显示，除 2024-06-24/25 附近疑似存在一个交易日归因差异的小簇样本外，该推导序列与官方份额变化高度一致。
- MCP 自然语言响应不适合五年每日批量提取，因此除非找到精确长历史份额指标，否则全区间历史继续使用 HTTP，MCP 用于抽样验证。

## 因子 IC 结果

前瞻收益窗口：21 个交易日。

| 因子 | 平均 IC | IC IR | 正 IC 占比 | 观测数 |
|---|---:|---:|---:|---:|
| 动量 | -0.0113 | -0.0317 | 48.21% | 1,064 |
| 资金流 | -0.0028 | -0.0101 | 52.17% | 1,127 |
| 拥挤度 | 0.0367 | 0.1350 | 54.17% | 1,128 |
| 基线综合得分 | 0.0044 | 0.0144 | 52.48% | 1,128 |

解读：

- 当前基线信号整体较弱，但略为正。
- 拥挤度是初始真实数据测试中唯一较明确的正贡献项。
- 当前 1M/3M/6M 权重和波动惩罚设定下，动量 IC 为负。
- 资金流已有 MCP 抽样验证支持，但在作为最终官方资金流因子前，仍需要更长窗口验证。

## 早期基线回测结果

回测设计：

- 每周五调仓
- 按基线综合得分选择前 5 只 ETF
- 等权，单只 ETF 上限 25%
- 单边换手交易成本 5bps
- 基准：`510300.SH`

输出文件：

- 因子得分：`data/factors/baseline_scores.parquet`
- 因子 IC：`data/factors/baseline_factor_ic.parquet`
- 回测曲线：`data/processed/baseline_backtest_curve.parquet`
- 回测权重：`data/processed/baseline_backtest_weights.parquet`
- 回测指标：`data/processed/baseline_backtest_metrics.json`

指标：

- 总收益：23.18%
- 年化收益：4.43%
- 年化波动：22.32%
- Sharpe：0.20
- 最大回撤：-33.16%
- 基准总收益：-4.51%
- 超额总收益：27.69%
- 信息比率：0.51
- 平均日换手：10.55%

该早期基线后来已被动量 Top3 候选替代；当前主策略见 `MOMENTUM_CANDIDATE_VALIDATION_RECORD.md`。

早期基线输出中的最新调仓持仓：

| 日期 | 资产 | 权重 |
|---|---:|---:|
| 2026-06-26 | `510500.SH` | 20% |
| 2026-06-26 | `159915.SZ` | 20% |
| 2026-06-26 | `159949.SZ` | 20% |
| 2026-06-26 | `159995.SZ` | 20% |
| 2026-06-26 | `515000.SH` | 20% |

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.validate
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.backtest
```

结果：

- 单元测试：10 个通过
- 数据校验：通过
- 回测：完成

环境说明：

- 在 Codex 环境中，`pyarrow` 会打印 `sysctlbyname` CPU 探测警告；Parquet 读写和所有验证步骤均已正常完成。

## 建议后续工作

1. 重新调优基线信号：降低或反转当前动量组件，并测试拥挤度主导的变体。
2. 将官方 MCP 份额变化提取扩展到更长滚动窗口，或定位精确的 HTTP/date-sequence 长历史 ETF 份额指标。
3. 加入估值、分析师一致预期景气和宏观共振因子，再判断策略是否达到研究闭环。
