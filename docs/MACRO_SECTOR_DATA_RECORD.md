# 宏观与行业数据记录

日期：2026-07-02

## 目标

继续推进原 ETF 轮动方案，补齐估值、景气和宏观共振因子所需的数据缺口。

本步骤重点包括：

- iFinD EDB 宏观指标
- 行业/指数日线行情
- 行业估值与一致预期/景气数据探测

## 已实现组件

新增代码和配置：

- `src/etf_rotation/data/ifind_mcp.py`
- `scripts/collect_ifind_research_data.py`
- `config/macro_indicators.json`
- `config/sector_indices.json`
- `tests/test_ifind_mcp_parser.py`

采集器支持：

- iFinD MCP 原始响应归档
- 标准 EDB 表格解析
- Markdown 表格解析
- `万`、`亿`、`万亿` 等中文数字单位解析
- 使用 3 个月行业指数窗口，减少 MCP 长区间截断
- 复用原始响应，支持中断后继续采集

## 宏观 EDB 数据

命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets macro
```

输出：

- `data/raw/macro_indicators.parquet`
- 原始响应目录：`data/raw/ifind_research_raw/macro/`

覆盖情况：

| 指标 | 行数 | 起始 | 结束 | 备注 |
|---|---:|---|---|---|
| 制造业 PMI | 66 | 2021-01-31 | 2026-06-30 | 月度 |
| CPI 同比 | 65 | 2021-01-31 | 2026-05-31 | 月度 |
| PPI 同比 | 65 | 2021-01-31 | 2026-05-31 | 月度 |
| M2 同比 | 65 | 2021-01-31 | 2026-05-31 | 月度 |
| 社融存量同比 | 65 | 2021-01-31 | 2026-05-31 | 月度 |
| 中国 10 年期国债收益率 | 1369 | 2021-01-04 | 2026-06-30 | 日度 |

结果：

- 宏观数据可用于宏观共振因子，以及后续 HMM/市场状态分类器研究。

## 行业指数数据

命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets sector_index --sector-window-months 3
```

输出：

- `data/raw/sector_index_daily.parquet`
- 原始响应目录：`data/raw/ifind_research_raw/sector_index/`

覆盖情况：

| 主题 | 指数代码 | 行数 | 起始 | 结束 | 限制 |
|---|---|---:|---|---|---|
| 券商 | `399975.SZ` | 1328 | 2021-01-04 | 2026-06-30 | 完整 |
| 消费 | `000932.SH` | 1328 | 2021-01-04 | 2026-06-30 | 60 个收盘价缺失 |
| 军工 | `399967.SZ` | 1328 | 2021-01-04 | 2026-06-30 | 完整 |
| 金融 | `000914.SH` | 1328 | 2021-01-04 | 2026-06-30 | 完整 |
| 基建 | `399995.SZ` | 1328 | 2021-01-04 | 2026-06-30 | 完整 |
| 有色金属 | `930708.CSI` | 1328 | 2021-01-04 | 2026-06-30 | 完整 |
| 医药 | `000933.SH` | 1328 | 2021-01-04 | 2026-06-30 | 使用中证800医药代理 |
| 半导体 | `931865.CSI` | 1235 | 2021-01-04 | 2026-06-30 | 早期记录较少 |
| 煤炭 | `H30596.CSI` | 1328 | 2021-01-04 | 2026-06-30 | 成交额缺失 |
| 地产 | `000006.SH` | 120 | 2021-01-29 | 2026-06-30 | 仅月度/稀疏 |
| 科技 | `931186.CSI` | 180 | 2021-01-29 | 2026-06-30 | 仅月度/稀疏 |

结果：

- 大多数行业指数收盘价序列可用。
- 地产和科技指数映射需要更好的日度指数代码，或暂时回退到 ETF 自身日线价格。
- 煤炭可用于价格动量，但无法从当前行业指数源计算成交额类拥挤度。

## 行业估值与一致预期探测

命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets sector_fundamental
```

输出：

- `data/raw/sector_fundamentals.parquet`
- 原始响应目录：`data/raw/ifind_research_raw/sector_fundamental/`

结果：

- 解析行数：0
- MCP `sector_data` 工具能识别 PE、PB、ROE、预测净利润、预测 EPS 等请求字段，但当前行业/指数查询返回空表。

当前判断：

- 这更可能是行业标识符问题，而不是数据一定不可用。
- 下一次应尝试使用精确 iFinD 板块代码，或从指数成分股/代表 ETF 持仓聚合行业估值和景气数据。

## 需要决策的数据问题

1. 当前 shell 没有配置 iFinD HTTP refresh token

   HTTP `cmd_history_quotation` 可能是更快、更精确的指数日线采集通道，但当前环境没有 `IFIND_REFRESH_TOKEN`。

2. 行业估值/一致预期需要确定标识符策略

   可选方案：

   - 向 iFinD/终端查询目标行业的精确板块代码。
   - 使用 ETF 持仓/指数成分股，聚合股票层面的 PE、PB、ROE 和一致预期。
   - 暂时推迟估值/景气因子，先推进宏观共振研究。

3. 地产和科技行业代理需要复核

   当前精确代码返回稀疏序列。这两个主题应使用更好的指数代码，或在行业指数映射改善前先使用 ETF 日线价格。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- 单元测试：31 个通过
