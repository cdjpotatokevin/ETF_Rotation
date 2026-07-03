# 第二阶段记录：基线因子与回测

日期：2026-06-30

## 范围

本阶段在第一阶段标准化 ETF 日线表之上，加入可运行的基线因子和回测层。

已实现的基线因子：

- 动量：1M、3M、6M 收益率，并加入 3M 波动惩罚。
- 资金流：ETF 份额的 1M 和 3M 变化率。
- 拥挤度：短期相对中期换手率和成交额热度的反向指标。

待完善因子：

- 估值
- 景气/分析师一致预期
- 宏观共振

这些待完善因子需要真实 iFinD 行业、财务和宏观数据支撑，才能进行可信验证。

## 已实现文件

- `src/etf_rotation/factors/common.py`
- `src/etf_rotation/factors/momentum.py`
- `src/etf_rotation/factors/fund_flow.py`
- `src/etf_rotation/factors/crowding.py`
- `src/etf_rotation/factors/scoring.py`
- `src/etf_rotation/backtest/engine.py`
- `src/etf_rotation/backtest/pipeline.py`
- `src/etf_rotation/cli/backtest.py`
- `tests/test_factors.py`
- `tests/test_backtest.py`

## 回测设计

- 频率：每周五调仓
- 选券：按基线得分选择前 5 只 ETF
- 加权：等权，单只 ETF 上限 25%
- 交易成本：单边换手 5bps
- 基准：默认 `510300.SH`

该阶段的基准设置后来已由用户正式确认为 `510300.SH` 沪深300ETF。

## 验证结果

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.backtest
```

结果：

- 单元测试：8 个通过
- 因子输出：`data/factors/baseline_scores.parquet`
- 回测曲线：`data/processed/baseline_backtest_curve.parquet`
- 回测权重：`data/processed/baseline_backtest_weights.parquet`
- 回测指标：`data/processed/baseline_backtest_metrics.json`

合成数据冒烟测试指标：

- 总收益：132.94%
- 年化收益：16.03%
- 年化波动：11.03%
- Sharpe：1.45
- 最大回撤：-12.40%
- 基准总收益：-0.42%
- 超额总收益：133.36%
- 信息比率：0.39
- 平均日换手：11.63%

这些数值来自可复现的合成数据，只用于工程验证，不构成投资证据。

## 下一步

真实 iFinD ETF 历史数据已经通过 HTTP API 接入。后续工程重点：

1. 接入行业估值和分析师一致预期字段。
2. 接入 PMI、CPI、PPI、M2、社融、利率等宏观序列。
3. 在本地配置 `IFIND_AUTH_TOKEN` 后，通过 MCP 获取官方 ETF 份额序列。

真实数据回测见 `REAL_IFIND_BACKTEST_RECORD.md`。
