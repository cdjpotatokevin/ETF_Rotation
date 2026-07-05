# ML 状态识别仓位 Overlay 记录

日期：2026-07-05

## 目标

测试“ML 不直接选 ETF，只判断动量组合该用 75% 仓位还是 Top3 满仓”的方案。

底层选券仍然保持当前线性动量规则：

- 动量规格：`m_1_3_6`
- 每周五调仓
- 选择 Top3
- 最低得分：`0.60`
- 防守仓位：单只 ETF `25%`，总权益仓位 75%，剩余现金
- 进攻仓位：单只 ETF `33.33%`，总权益仓位 100%
- 交易成本：单边 `5bps`
- 基准：`510300.SH` 沪深300ETF

ML 只做一个判断：下一期是否适合从 75% 仓位切换到 Top3 满仓。

## 方法

每个周五先用原动量规则选出 Top3，再构造组合层面的状态特征：

- 入选 ETF 数量
- 入选 ETF 的平均/最低动量分数
- 入选 ETF 分数差
- 入选 ETF 的平均原始动量
- 入选 ETF 的 21/63/126 日收益
- 入选 ETF 的 63 日波动和回撤
- 入选 ETF 相对沪深300ETF的 21 日强弱
- 沪深300ETF 的 21/63 日收益、63 日波动、63 日回撤

训练目标：

- 如果下一周 Top3 篮子平均收益为正，则标记为 `target_full = 1`
- 否则标记为 `target_full = 0`

模型：

- Logistic 回归
- 无新增外部依赖，使用项目内 `numpy/pandas` 实现
- 滚动样本外训练和测试，不使用随机切分

测试阈值：

- `0.50`
- `0.55`
- `0.60`
- `0.65`

当模型预测满仓概率大于等于阈值时，用 Top3 满仓；否则回到 75% 仓位。

## 输出文件

- `data/processed/ml_regime_overlay/regime_decision_frame.parquet`
- `data/processed/ml_regime_overlay/ml_regime_walk_forward.parquet`
- `data/processed/ml_regime_overlay/ml_regime_walk_forward.csv`
- `data/processed/ml_regime_overlay/ml_regime_summary.parquet`
- `data/processed/ml_regime_overlay/ml_regime_summary.csv`
- `data/processed/ml_regime_overlay/latest_ml_regime_weights.parquet`
- `data/processed/ml_regime_overlay/latest_ml_regime_probability.parquet`
- `data/processed/ml_regime_overlay/summary.json`

## 滚动样本外汇总

由于 2022 年之前可用训练标签不足，本次有效样本外区间从 2023 年开始。

| 方案 | 平均测试收益 | 平均 Sharpe | 最差回撤 | 平均超额收益 | 平均信息比率 | 满仓触发比例 |
|---|---:|---:|---:|---:|---:|---:|
| ML overlay，阈值0.50 | 27.20% | 1.65 | -14.25% | 19.63% | 1.63 | 23.73% |
| 固定75%仓位 | 21.91% | 1.40 | -14.05% | - | 1.40 | 0% |
| 固定Top3满仓 | 29.43% | 1.46 | -18.44% | - | 1.51 | 100% |

不同阈值对比：

| 阈值 | ML平均收益 | ML平均Sharpe | ML最差回撤 | 满仓触发比例 |
|---:|---:|---:|---:|---:|
| 0.50 | 27.20% | 1.65 | -14.25% | 23.73% |
| 0.55 | 21.82% | 1.38 | -14.05% | 5.80% |
| 0.60 | 21.68% | 1.38 | -14.05% | 1.58% |
| 0.65 | 22.07% | 1.41 | -14.05% | 0.53% |

## 分年度结果

阈值 `0.50` 的结果：

| 测试期 | ML收益 | 固定75%收益 | 固定满仓收益 | ML最大回撤 |
|---|---:|---:|---:|---:|
| 2023 | 0.05% | 0.05% | -0.31% | -11.77% |
| 2024 | 35.74% | 29.85% | 39.87% | -13.95% |
| 2025 | 28.96% | 27.33% | 36.75% | -14.05% |
| 2026H1 | 44.03% | 30.40% | 41.42% | -14.25% |

## 最新信号

最新日期：`2026-07-03`。

- 最优阈值：`0.50`
- 预测满仓概率：`0.4598`
- 判断：低于阈值，维持 75% 仓位

最新组合：

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

## 解读

这个方向比“ML 直接预测 ETF 排名”更有效。

关键观察：

- ML overlay 相比固定 75% 仓位有提升：平均测试收益从 `21.91%` 提高到 `27.20%`，平均 Sharpe 从 `1.40` 提高到 `1.65`。
- ML overlay 的最差回撤 `-14.25%`，明显好于固定满仓的 `-18.44%`，接近固定 75% 仓位的 `-14.05%`。
- ML overlay 的平均收益仍略低于固定满仓的 `29.43%`，但风险调整表现更好。
- 阈值 `0.50` 表现最好，说明模型需要适度进攻；阈值过高时几乎不触发满仓，效果接近固定 75% 仓位。

## 结论

ML 作为状态识别/仓位控制层是有希望的。

但目前样本外区间只有 2023-2026H1 四段，样本仍少，因此不建议立即替代主策略。更稳妥的处理是：

- 当前主策略仍保留 `Top3 + 25%上限 + 现金`
- 将 `ML regime overlay` 作为重点候选分支继续跟踪
- 后续增加市场宽度、宏观 overlay、成交额趋势等特征后，再决定是否提升为主策略

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_ml_regime_overlay.py
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- ML 状态 overlay 评估完成
- 单元测试：48 个通过
