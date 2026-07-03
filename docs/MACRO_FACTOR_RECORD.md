# 宏观因子记录

日期：2026-07-02

## 目标

使用新采集的 iFinD 宏观 EDB 数据，实现第一版透明的宏观共振因子。

本步骤目标不是优化信号，而是在加入主策略前，先检验一个简单规则型宏观映射是否具备独立预测价值。

## 已实现组件

新增代码：

- `src/etf_rotation/factors/macro.py`
- `scripts/evaluate_macro_factor.py`
- `tests/test_macro_factor.py`

更新：

- `src/etf_rotation/factors/ic.py` 已加入 `macro_resonance_score`，并可动态识别额外的 `*_score` 列。

## 因子逻辑

第一版使用透明的宏观组件：

- 增长：PMI、社融、M2，扣除 10 年国债收益率压力。
- 通胀：CPI 和 PPI。
- 流动性：M2 和社融，扣除 10 年国债收益率压力。
- 避险：弱增长叠加收益率/通胀压力。

每个宏观指标使用滚动 z-score 标准化。ETF 主题再按固定暴露映射到宏观组件，例如：

- 成长和科技主题偏好增长与流动性。
- 资源主题偏好通胀。
- 防御主题偏好避险。
- 红利低波偏好避险与通胀。

每日横截面排序后的得分记为 `macro_resonance_score`。

## 命令

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_factor.py
```

输出：

- `data/processed/macro_factor/macro_scores.parquet`
- `data/processed/macro_factor/macro_factor_ic.parquet`
- `data/processed/macro_factor/macro_backtest_curve.parquet`
- `data/processed/macro_factor/macro_backtest_weights.parquet`
- `data/processed/macro_factor/macro_factor_metrics.json`

## 结果

测试的宏观混合权重：

| 因子 | 权重 |
|---|---:|
| 动量 | 45% |
| 资金流 | 20% |
| 拥挤度 | 20% |
| 宏观共振 | 15% |

回测结果：

| 指标 | 数值 |
|---|---:|
| 总收益 | 0.05% |
| 年化收益 | 0.01% |
| Sharpe | 0.00 |
| 最大回撤 | -40.53% |
| 基准总收益 | -4.51% |
| 超额总收益 | 4.56% |
| 信息比率 | 0.15 |

IC 结果：

| 因子 | 平均 IC | IC IR | 正 IC 占比 |
|---|---:|---:|---:|
| 宏观共振 | -0.0343 | -0.0909 | 47.01% |
| 动量 | -0.0113 | -0.0317 | 48.21% |
| 资金流 | -0.0028 | -0.0101 | 52.17% |
| 拥挤度 | 0.0367 | 0.1350 | 54.17% |
| 宏观混合基线 | -0.0107 | -0.0334 | 49.37% |

## 解读

宏观数据层是可用的，但第一版规则型宏观共振映射还不适合进入主策略。

关键发现：

- 宏观因子在当前 ETF 池和样本区间中 IC 为负。
- 以 15% 权重加入后，明显恶化基线回测表现。
- 结果可能反映宏观数据的滞后性和市场状态不稳定：宏观数据多为月度/低频，而 A 股行业与风格 ETF 轮动更快。
- 从宏观状态到 ETF 主题的静态映射过于刚性。

## 建议

暂不把该宏观排序因子加入主候选。

后续宏观研究应测试：

- 低频用法：改为月度或季度风险/仓位 overlay，而不是每周横截面排序因子。
- 状态过滤：只控制权益总仓位或防御倾斜，不直接参与行业排序。
- 带样本外验证的 HMM/状态分类器。
- 反向宏观解释只作为诊断，不作为立即上线的生产改动。

当前主候选仍为 `m_1_3_6_top3_min0p6`。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_factor.py
```

结果：

- 单元测试：34 个通过
- 宏观因子评估已基于真实 iFinD ETF 和宏观数据完成
