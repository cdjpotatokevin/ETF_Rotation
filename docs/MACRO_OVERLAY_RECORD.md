# 宏观风险 Overlay 记录

日期：2026-07-02

## 目标

将宏观模块从“每周横截面排序因子”改为“低频风险/仓位 overlay”。

该 overlay 不改变 ETF 选择，只缩放当前主候选策略的总权益仓位：

- 候选：`m_1_3_6_top3_min0p6`
- 基础选择：每周 Top 3 动量
- 基准：`510300.SH`
- 宏观数据：iFinD EDB

## 已实现组件

新增代码：

- `src/etf_rotation/backtest/macro_overlay.py`
- `scripts/evaluate_macro_overlay.py`
- `tests/test_macro_overlay.py`

输出：

- `data/processed/macro_overlay/macro_overlay_grid.parquet`
- `data/processed/macro_overlay/macro_overlay_grid.csv`
- `data/processed/macro_overlay/macro_overlay_summary.json`
- `data/processed/macro_overlay/best_macro_overlay_curve.parquet`
- `data/processed/macro_overlay/best_macro_overlay_weights.parquet`
- `data/processed/macro_overlay/best_macro_overlay_signal.parquet`

## 方法

宏观 overlay 使用上一版宏观因子的同一组宏观组件，但只作用于总仓位。

风险分数含义：

- 增长和流动性较弱时上升。
- 通胀和避险压力较高时上升。
- 为降低前视风险，宏观日期向后平移 `10` 个自然日后才生效。

默认参数网格：

- 中风险阈值：`0.35`、`0.50`、`0.75`
- 高风险阈值：`0.75`、`0.85`、`1.00`、`1.25`、`1.50`
- 中风险仓位：`90%`、`75%`
- 高风险仓位：`75%`、`50%`

## 最优 Overlay

最优键：

- `med0p75_high1p5_me0p9_he0p75_lag10`

配置：

- 中风险阈值：`0.75`
- 高风险阈值：`1.50`
- 中风险仓位：`90%`
- 高风险仓位：`75%`
- 宏观发布滞后：`10` 天

平均目标仓位：

- `97.10%`

风险天数：

- 高风险天数：`68`
- 中风险天数：`181`

## 最新信号与组合

最新宏观信号日期：`2026-06-30`。

- 宏观风险分数：`0.2596`
- 目标仓位：`100%`
- 当前结论：不触发额外降仓

最近一次组合调仓日：`2026-06-26`。

| 资产 | 名称 | Overlay 后权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

## 全样本对比

| 指标 | 主候选 | 宏观 Overlay |
|---|---:|---:|
| 总收益 | 94.08% | 91.43% |
| 年化收益 | 14.80% | 14.47% |
| 年化波动 | 19.44% | 19.25% |
| Sharpe | 0.76 | 0.75 |
| 最大回撤 | -17.02% | -17.02% |
| 超额收益 | 98.59% | 95.94% |
| 信息比率 | 1.14 | 1.12 |
| 平均换手 | 5.92% | 5.89% |

解读：

- overlay 没有改善全样本最大回撤。
- overlay 略微降低收益和波动。
- 与此前“每周宏观排序因子”不同，overlay 能保留主候选的大部分收益轮廓。

## 滚动样本外结果

| 测试期 | 测试收益 | Sharpe | 最大回撤 | 超额收益 |
|---|---:|---:|---:|---:|
| 2022 | -12.97% | -0.79 | -15.04% | 8.11% |
| 2023 | -0.14% | -0.01 | -11.77% | 11.25% |
| 2024 | 30.09% | 1.27 | -13.95% | 13.62% |
| 2025 | 28.82% | 1.53 | -12.35% | 7.23% |
| 2026H1 | 28.67% | 2.79 | -13.39% | 25.05% |

与主候选相比：

- 2025 年最大回撤从约 `-14.05%` 改善到 `-12.35%`。
- 2026H1 最大回撤从约 `-13.47%` 小幅改善到 `-13.39%`。
- 2022 年最大回撤从约 `-14.48%` 变差到 `-15.04%`。

## 建议

保留该 overlay 作为可选防守分支，不作为主基线。

原因：

- 它比“宏观作为每周排序因子”的表现稳定得多。
- 它在部分区间有帮助，尤其是 2025 年。
- 但它尚未证明能显著改善全样本最大回撤，因此不足以替代主候选。

下一步研究：

- 仅在组合自身回撤/波动也确认风险时才触发 overlay。
- 测试仓位变化只按月执行。
- 加入市场宽度或基准趋势确认，减少宏观误降仓。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_overlay.py
```

结果：

- 单元测试：36 个通过
- 宏观 overlay 评估已基于真实 iFinD ETF 和宏观数据完成
