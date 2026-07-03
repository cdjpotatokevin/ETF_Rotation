# 动量与风险控制调参记录

日期：2026-07-01

## 目标

在上一轮发现高动量暴露在 2025-2026 测试期表现较好的基础上，继续测试稳健性：

- 不同动量窗口
- 趋势过滤
- Top-N 集中度
- 最低得分门槛
- 组合层面止损
- 波动率目标缩放

基准保持为 `510300.SH` 沪深300ETF。

## 已实现组件

新增代码：

- `src/etf_rotation/factors/momentum_variants.py`
- `src/etf_rotation/backtest/risk_control.py`
- `scripts/tune_momentum_risk.py`
- `tests/test_momentum_risk.py`

回测引擎新增支持：

- 在 ETF 选择前使用 `min_score` 过滤。
- 通过 `run_weighted_backtest` 使用外部传入的风险调整后权重。

## 核心参数网格

命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/tune_momentum_risk.py --train-end 2024-12-31 --test-start 2025-01-01 --min-scores none,0.60 --target-vols none,0.18 --stop-losses none,0.18 --output-dir data/processed/momentum_risk_tuning_core
```

输出：

- `data/processed/momentum_risk_tuning_core/momentum_risk_grid.parquet`
- `data/processed/momentum_risk_tuning_core/momentum_risk_grid.csv`
- `data/processed/momentum_risk_tuning_core/best_momentum_risk.json`
- `data/processed/momentum_risk_tuning_core/best_momentum_risk_curve.parquet`

网格维度：

- 动量规格：6 组
- Top N：3、5
- 最低得分：无、0.60
- 目标波动：无、0.18
- 止损阈值：无、0.18

## 最优候选

最优键：

- `m_1_3_6_top3_min0p6_volnone_stopnone`

配置：

- 动量规格：1M/3M/6M 加权动量，并加入波动惩罚
- Top N：3
- 最低得分：0.60
- 目标波动缩放：无
- 组合止损：无

指标：

| 区间 | 总收益 | 年化收益 | Sharpe | 最大回撤 | 超额收益 | 信息比率 |
|---|---:|---:|---:|---:|---:|---:|
| 训练期 | 17.90% | 4.99% | 0.28 | -14.48% | 41.38% | 0.98 |
| 测试期 | 70.63% | 45.51% | 2.00 | -14.05% | 42.24% | 1.53 |
| 全样本 | 94.08% | 14.80% | 0.76 | -17.02% | 98.59% | 1.14 |

## 与上一轮候选对比

上一轮因子权重调参最优候选：

- 纯动量、Top 5、无得分门槛
- 全样本 Sharpe：0.54
- 全样本最大回撤：-29.36%
- 全样本总收益：84.47%

新最优候选：

- 动量 Top 3，得分门槛 0.60
- 全样本 Sharpe：0.76
- 全样本最大回撤：-17.02%
- 全样本总收益：94.08%

解读：

- 得分门槛贡献了最重要的风险控制效果，使策略避免进入相对强度不足的标的。
- Top 3 集中度相较 Top 5 提高了信号质量。
- 显式止损没有改善最优结果，因为入选候选没有以有益方式触发测试阈值。
- 波动率目标缩放在部分变体中降低了回撤，但也削弱了上行收益，未能胜出。

## 强备选

| 候选 | 全样本 Sharpe | 全样本最大回撤 | 测试期 Sharpe | 备注 |
|---|---:|---:|---:|---|
| `m_3_6_trend_top3_min0p6_volnone_stopnone` | 0.78 | -16.08% | 2.03 | 全样本 Sharpe 最高且回撤更低，但综合目标略低 |
| `m_3_6_top3_min0p6_volnone_stopnone` | 0.68 | -20.59% | 2.09 | 测试期强，训练期回撤较弱 |
| `m_1_3_6_top3_min0p6_vol0p18_stopnone` | 0.77 | -14.35% | 1.94 | 前列候选中回撤控制最好 |

## 建议

进入深入研究的两条候选：

1. 主分支：`m_1_3_6_top3_min0p6_volnone_stopnone`
2. 防守分支：`m_3_6_trend_top3_min0p6_volnone_stopnone`

后续测试重点：

- 滚动样本外切分，而不是只看一次训练/测试切分。已在 `MOMENTUM_CANDIDATE_VALIDATION_RECORD.md` 完成。
- 月度与周度调仓对比。已在 `MOMENTUM_CANDIDATE_VALIDATION_RECORD.md` 完成。
- 交易成本敏感性。已在 `MOMENTUM_CANDIDATE_VALIDATION_RECORD.md` 完成。
- 接入宏观/估值因子后，测试其与动量门槛的组合效果。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- 加入候选验证后，单元测试 25 个通过
