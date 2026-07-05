# 机器学习模型验证记录

日期：2026-07-05

## 目标

检验轻量机器学习预测模型是否能替代或改进当前线性动量规则。

本次实验保持保守约束：

- 不新增外部依赖，仅使用 `numpy` 和 `pandas`。
- 不做随机切分，只做滚动样本外验证。
- 不直接训练复杂模型，先测试可解释的轻量模型。
- 交易规则保持与当前主策略一致：每周五调仓、Top3、最低分数 `0.60`、单只 ETF 上限 `25%`、单边交易成本 `5bps`。
- 基准：`510300.SH` 沪深300ETF。
- 预测目标：未来 21 个交易日收益或是否进入未来收益前 30%。

## 模型

| 模型键 | 说明 |
|---|---|
| `linear_momentum_rule` | 当前线性动量规则，作为基准 |
| `ridge_return` | Ridge 回归预测未来 21 日收益 |
| `logistic_top` | Logistic 回归预测未来收益是否进入前 30% |
| `ridge_interaction` | Ridge 回归加少量交互项，作为轻量非线性雏形 |

## 特征

模型使用历史价格、成交额和相对强弱特征：

- 5/21/63/126 日收益
- 21/63 日波动率
- 63 日回撤
- 成交额热度
- 相对沪深300ETF的 21 日强弱
- 沪深300ETF 21 日收益
- 当前线性动量原始值
- 交互项模型额外加入少量收益、波动、相对强弱交互

## 验证方式

滚动样本外切分：

- 训练至 2021 年底，测试 2022 年
- 训练至 2022 年底，测试 2023 年
- 训练至 2023 年底，测试 2024 年
- 训练至 2024 年底，测试 2025 年
- 训练至 2025 年底，测试 2026H1

最新信号使用“已经能计算未来 21 日收益标签”的历史样本训练，再预测 `2026-07-03`。

## 输出文件

- `data/processed/ml_model_evaluation/ml_walk_forward.parquet`
- `data/processed/ml_model_evaluation/ml_walk_forward.csv`
- `data/processed/ml_model_evaluation/ml_model_summary.parquet`
- `data/processed/ml_model_evaluation/ml_model_summary.csv`
- `data/processed/ml_model_evaluation/ml_latest_weights.parquet`
- `data/processed/ml_model_evaluation/ml_latest_weights.csv`
- `data/processed/ml_model_evaluation/ml_latest_scores.parquet`
- `data/processed/ml_model_evaluation/summary.json`

## 汇总结果

| 模型 | 平均测试收益 | 平均 Sharpe | 最差回撤 | 平均超额收益 | 平均信息比率 | 平均 Rank IC | 正收益期数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 当前线性动量规则 | 14.97% | 0.97 | -14.48% | 13.13% | 1.25 | -0.245 | 4/5 |
| Ridge 预测21日收益 | -9.93% | -0.77 | -28.66% | -11.77% | -1.22 | 0.273 | 1/5 |
| Logistic 预测前30%概率 | -10.54% | -0.85 | -28.53% | -12.38% | -1.28 | 0.273 | 1/5 |
| Ridge 加交互项 | -11.66% | -0.86 | -28.38% | -13.50% | -1.35 | 0.277 | 1/5 |

## 样本外组合表现

| 模型 | 2022 | 2023 | 2024 | 2025 | 2026H1 |
|---|---:|---:|---:|---:|---:|
| 当前线性动量规则 | -12.77% | 0.05% | 29.85% | 27.33% | 30.40% |
| Ridge 预测21日收益 | -27.11% | -14.26% | -6.77% | 11.89% | -13.39% |
| Logistic 预测前30%概率 | -25.12% | -15.48% | -6.83% | 7.59% | -12.86% |
| Ridge 加交互项 | -23.57% | -12.35% | -15.02% | 6.66% | -14.02% |

## 最新信号

最新预测日期：`2026-07-03`。

当前线性动量规则：

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

三个 ML 模型最新都倾向同一组防御/地产相关组合：

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159768.SZ` | 地产ETF | 25% |
| `159928.SZ` | 消费ETF | 25% |
| `515710.SH` | 食品ETF | 25% |
| `CASH` | 现金 | 25% |

## 解读

本次实验不支持用轻量 ML 模型替代当前线性动量规则。

关键观察：

- ML 模型的平均 Rank IC 为正，但转成 Top3 周度组合后表现很差。这说明“平均排序相关”没有直接转化为可交易组合收益。
- ML 模型明显偏向防御/低弹性资产，在 2024-2026 的成长/科技趋势行情中严重错失主线。
- 样本量仍然偏小，19 只 ETF、约 5 年历史，对监督学习模型并不友好。
- 交互项 Ridge 没有改善结果，说明简单非线性扩展也没有带来稳定收益。

## 结论

当前主策略继续保留线性动量规则，不提升 ML 模型为主分支。

后续如果继续研究 ML，更适合把它放在风险控制层，而不是直接预测 ETF 排名：

- 判断什么时候使用 75% 仓位，什么时候使用 Top3 满仓。
- 判断动量策略是否处在高胜率市场状态。
- 与宏观 overlay、市场宽度、基准趋势结合，做状态识别。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_ml_models.py
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- ML 模型滚动样本外评估完成
- 单元测试：43 个通过
