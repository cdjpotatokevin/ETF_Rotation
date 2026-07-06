# 扩展 A 股 ETF 池回测记录

日期：2026-07-06

## 目标

按用户确认的投资范围，建立一个独立的新版本回测：

- 不直接混入当前主策略。
- 不加入跨境、黄金、债券 ETF。
- 只扩展 A 股股票 ETF。
- 原 19 只 ETF 池继续作为主策略默认池。

## 已完成

新增扩展池配置：

- `config/etf_pool_expanded_a_share.json`

新增扩展池评估脚本：

- `scripts/evaluate_expanded_pool.py`
- `scripts/evaluate_expanded_ml_regime_overlay.py`

新增测试：

- `tests/test_expanded_pool_backtest.py`
- `tests/test_config.py` 中增加扩展池配置校验

扩展池包含 29 只 ETF：

- 原始 19 只 ETF
- 新增 10 只 A 股股票 ETF：`588000.SH`、`512800.SH`、`512690.SH`、`515030.SH`、`515790.SH`、`159819.SZ`、`512980.SH`、`516020.SH`、`159611.SZ`、`159865.SZ`

## 当前数据状态

新增 10 只 ETF 的代码此前已通过 iFinD MCP `fund.get_fund_profile` 做过识别校验，均可返回基金资料。

`2026-07-06` 已使用 iFinD HTTP 历史行情接口成功补齐新增 10 只 ETF 的真实日线行情：

- 数据区间：`2021-01-04` 至 `2026-07-03`
- 新增 ETF 数量：10 只
- 新增日线记录：12,983 行
- 合并后扩展池数量：29 只

新增行情已保存为独立文件，不覆盖当前主策略默认数据：

- `data/raw/expanded_a_share_new_etf_daily.parquet`

新增 ETF 的可用日线数量：

| ETF代码 | 名称 |
|---|---|
| `159611.SZ` | 电力ETF |
| `159819.SZ` | 人工智能ETF |
| `159865.SZ` | 养殖ETF |
| `512690.SH` | 酒ETF |
| `512800.SH` | 银行ETF |
| `512980.SH` | 传媒ETF |
| `515030.SH` | 新能源车ETF |
| `515790.SH` | 光伏ETF |
| `516020.SH` | 化工ETF |
| `588000.SH` | 科创50ETF |

## 全样本结果

回测区间：`2021-01-01` 至 `2026-07-03`。基准：`510300.SH` 沪深300ETF。

| 版本 | 方案 | 总收益 | 年化收益 | 年化波动 | Sharpe | 最大回撤 | 信息比率 | 平均日换手 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 原19只ETF池 | Top3 25%上限+现金 | 80.09% | 12.99% | 19.60% | 0.66 | -17.02% | 1.06 | 5.91% |
| 扩展A股ETF池 | Top3 25%上限+现金 | 105.99% | 14.66% | 21.88% | 0.67 | -19.56% | 0.99 | 6.74% |
| 原19只ETF池 | Top3满仓 | 110.33% | 16.69% | 26.14% | 0.64 | -22.49% | 1.09 | 7.88% |
| 扩展A股ETF池 | Top3满仓 | 147.66% | 18.73% | 29.17% | 0.64 | -26.25% | 0.99 | 8.99% |
| 原19只ETF池 | Top4满仓 | 65.66% | 11.05% | 25.63% | 0.43 | -28.05% | 0.82 | 7.37% |
| 扩展A股ETF池 | Top4满仓 | 91.83% | 13.13% | 26.65% | 0.49 | -24.27% | 0.85 | 8.64% |

## 最新信号

最新数据日期：`2026-07-03`。

当前主策略仍使用原 19 只 ETF 池，最新推荐不变：

| ETF代码 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

扩展 A 股 ETF 池的新版本信号如下：

| ETF代码 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `588000.SH` | 科创50ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `CASH` | 现金 | 25% |

## 初步结论

扩展池确实提高了收益弹性：主分支 `Top3 25%上限+现金` 的总收益从 `80.09%` 提高到 `105.99%`，年化收益从 `12.99%` 提高到 `14.66%`。

代价也明确：最大回撤从 `-17.02%` 扩大到 `-19.56%`，年化波动从 `19.60%` 提高到 `21.88%`，平均日换手从 `5.91%` 提高到 `6.74%`。信息比率从 `1.06` 降至 `0.99`，说明扩池后的收益提升更多来自成长/科技弹性的增强，而不是稳定超额效率的全面提升。

因此目前不建议立即替换当前主策略。更稳妥的处理是：

- 当前主策略继续使用原 19 只 ETF 池。
- 扩展 A 股 ETF 池作为增强候选版本继续跟踪。
- 需要继续观察扩展池的风格集中度，尤其是科技、芯片、科创和 AI 暴露。

## ML Regime Overlay

已将扩展 A 股 ETF 池接入 ML regime overlay。

测试逻辑：

- 选券仍使用扩展池的动量 Top3。
- ML 不直接选 ETF，只判断下期是否从 75% 仓位切换到 Top3 满仓。
- 对比基准为扩展池固定 75% 仓位和扩展池固定 Top3 满仓。
- 样本外区间从 2022 年开始，阈值测试 `0.50`、`0.55`、`0.60`、`0.65`。

样本外汇总：

| 方案 | 平均测试收益 | 平均 Sharpe | 最差回撤 | 满仓触发比例 |
|---|---:|---:|---:|---:|
| ML overlay，阈值0.55 | 17.63% | 1.12 | -19.81% | 14.88% |
| 固定75%仓位 | 16.12% | 1.01 | -17.56% | 0% |
| 固定Top3满仓 | 21.15% | 1.04 | -23.24% | 100% |

不同阈值结果：

| 阈值 | ML平均收益 | ML平均Sharpe | ML最差回撤 | 满仓触发比例 |
|---:|---:|---:|---:|---:|
| 0.55 | 17.63% | 1.12 | -19.81% | 14.88% |
| 0.65 | 16.06% | 0.99 | -17.56% | 7.65% |
| 0.60 | 16.06% | 1.00 | -18.31% | 11.47% |
| 0.50 | 16.55% | 0.91 | -20.07% | 26.82% |

最新 ML overlay 信号日期：`2026-07-03`。

- 最优阈值：`0.55`
- 预测满仓概率：`0.4357`
- 判断：低于阈值，维持 75% 仓位

最新扩展池 ML overlay 组合：

| ETF代码 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `588000.SH` | 科创50ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `CASH` | 现金 | 25% |

ML overlay 的效果比较微妙：

- 相比固定满仓，ML overlay 把最差回撤从 `-23.24%` 降到 `-19.81%`，确实压住了满仓风险。
- 相比固定 75% 仓位，ML overlay 的平均收益从 `16.12%` 提高到 `17.63%`，平均 Sharpe 从 `1.01` 提高到 `1.12`。
- 但 ML overlay 的最差回撤 `-19.81%` 仍高于固定 75% 仓位的 `-17.56%`，说明它不是纯防守增强，而是“有限进攻 + 可控回撤”的折中。

因此，扩展池 ML overlay 可以作为增强候选，但仍不建议直接替代当前主策略。若后续要提升为主策略，需要加入更强的回撤约束，例如市场宽度、宏观风险、行业集中度或科技拥挤度特征。

## 运行方式

配置好 iFinD HTTP 刷新令牌后运行：

```bash
export IFIND_REFRESH_TOKEN="..."
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_expanded_pool.py --fetch-missing
```

脚本会将新增 ETF 的历史日线保存为独立文件：

- `data/raw/expanded_a_share_new_etf_daily.parquet`

然后生成扩展池独立结果：

- `data/processed/expanded_a_share_pool/expanded_a_share_etf_daily.parquet`
- `data/processed/expanded_a_share_pool/pool_comparison_metrics.csv`
- `data/processed/expanded_a_share_pool/pool_comparison_walk_forward.csv`
- `data/processed/expanded_a_share_pool/latest_pool_comparison_weights.csv`
- `data/processed/expanded_a_share_pool/summary.json`

运行扩展池 ML overlay：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_expanded_ml_regime_overlay.py
```

输出文件：

- `data/processed/expanded_a_share_ml_regime_overlay/expanded_ml_regime_summary.csv`
- `data/processed/expanded_a_share_ml_regime_overlay/expanded_ml_regime_walk_forward.csv`
- `data/processed/expanded_a_share_ml_regime_overlay/latest_expanded_ml_regime_weights.parquet`
- `data/processed/expanded_a_share_ml_regime_overlay/latest_expanded_ml_regime_probability.parquet`
- `data/processed/expanded_a_share_ml_regime_overlay/summary.json`

## 风控处理

脚本默认要求扩展池 29 只 ETF 都有历史行情。如果新增 ETF 数据缺失，会中止并输出缺失代码，不运行回测。

只有显式传入 `--allow-incomplete` 时，脚本才允许在数据不完整的情况下运行。这只适合调试，不适合正式研究结论。

## 下一步

继续为扩展池 ML overlay 增加市场宽度、宏观风险、行业集中度和科技拥挤度特征，验证能否在保留收益提升的同时把最差回撤压回固定 75% 仓位附近。
