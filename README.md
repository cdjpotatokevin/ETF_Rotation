# ETF 轮动

A 股行业与风格 ETF 轮动研究系统。

## 当前主策略

当前主策略为 `m_1_3_6_top3_min0p6`：

- 因子：1M/3M/6M 加权动量，并加入波动惩罚。
- 选券：每周五调仓，选择得分最高的 3 只 ETF。
- 门槛：最低得分 `0.60`。
- 权重：单只 ETF 上限 `25%`，未使用资金留在现金。
- 交易成本：单边 `5bps`。
- 基准：`510300.SH` 沪深300ETF。

截至当前已接入的真实 iFinD ETF 数据，最新数据日期为 `2026-07-03`，最近一次组合调仓日为 `2026-07-03`：

| 资产 | 名称 | 权重 |
|---|---|---:|
| `159995.SZ` | 芯片ETF | 25% |
| `515000.SH` | 科技ETF | 25% |
| `159915.SZ` | 创业板ETF | 25% |
| `CASH` | 现金 | 25% |

宏观风险 overlay 最新信号日期为 `2026-07-03`，宏观风险分数为 `0.3620`，目标仓位为 `100%`。因此当前 overlay 不触发降仓，组合仍保持上述 75% ETF 仓位与 25% 现金。

数据说明：`2026-07-01` 至 `2026-07-03` 的 ETF 收盘价和成交额通过 iFinD MCP `fund.get_fund_market_performance` 补入；此前历史数据仍来自 iFinD HTTP `cmd_history_quotation`。

## 快速开始

需要 Python 环境安装 `pandas`、`numpy`、`pyarrow` 等依赖：

```bash
python -m pip install -e ".[dev]"
python -m etf_rotation.cli.collect --provider synthetic
python -m etf_rotation.cli.validate
python -m etf_rotation.cli.backtest
python -m unittest discover -s tests
```

如果使用 iFinD，请在本地复制 `.env.example` 为 `.env`，或在 shell 中导出 token。真实 token 不要提交到代码仓库。

```bash
export IFIND_AUTH_TOKEN="..."
export IFIND_REFRESH_TOKEN="..."
```

然后可以采集真实 HTTP 历史 ETF 行情：

```bash
python -m etf_rotation.cli.collect --provider ifind-http
python -m etf_rotation.cli.validate
python -m etf_rotation.cli.backtest
```

配置好 `~/.config/ifind/mcp_config.json` 后，可以通过 MCP 提取官方 ETF 份额变化数据：

```bash
python scripts/extract_mcp_share_data.py --start 2026-06-22 --end 2026-06-30
```

年度样本窗口、权重调参、候选策略验证与宏观 overlay 评估命令如下：

```bash
python scripts/extract_mcp_share_data.py --windows 2022-06-22:2022-06-30,2023-06-21:2023-06-30,2024-06-21:2024-06-28,2025-06-23:2025-06-30,2026-06-22:2026-06-30 --output data/raw/etf_mcp_share_changes_annual_june.parquet --raw-dir data/raw/mcp_share_raw_annual_june
python scripts/tune_factor_weights.py --train-end 2024-12-31 --test-start 2025-01-01 --step 0.1
python scripts/tune_momentum_risk.py --train-end 2024-12-31 --test-start 2025-01-01 --min-scores none,0.60 --target-vols none,0.18 --stop-losses none,0.18 --output-dir data/processed/momentum_risk_tuning_core
python scripts/validate_momentum_candidate.py
python scripts/collect_ifind_research_data.py --datasets macro
python scripts/collect_ifind_research_data.py --datasets sector_index --sector-window-months 3
python scripts/evaluate_macro_factor.py
python scripts/evaluate_macro_overlay.py
```

## 已确认设定

- 项目目录：`/Users/sweethome/Qoder/etf-rotation`
- 存储方式：本地 Parquet 文件
- 回测区间：`2021-01-01` 至 `2026-07-03`
- ETF 池：方案中的行业 ETF 与风格 ETF 池
- 基准：`510300.SH` 沪深300ETF

## 当前研究结论

当前主候选 `m_1_3_6_top3_min0p6` 在真实 iFinD ETF 历史数据上的全样本结果：

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

宏观 EDB 数据和大部分行业指数日线已通过 iFinD MCP 接入。第一版“宏观共振横截面排序因子”因 IC 和回测贡献较弱，暂不纳入主策略。随后实现的“低频宏观风险/仓位 overlay”表现更稳，但全样本最大回撤改善不足，因此保留为可选防守分支，不替代主策略。

更多细节见：

- `docs/MOMENTUM_CANDIDATE_VALIDATION_RECORD.md`
- `docs/ALLOCATION_VARIANT_RECORD.md`
- `docs/ML_MODEL_EVALUATION_RECORD.md`
- `docs/ML_REGIME_OVERLAY_RECORD.md`
- `docs/ETF_POOL_EXPANSION_RECORD.md`
- `docs/MACRO_FACTOR_RECORD.md`
- `docs/MACRO_OVERLAY_RECORD.md`
- `docs/MACRO_SECTOR_DATA_RECORD.md`
