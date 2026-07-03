# iFinD MCP 数据提取记录

日期：2026-06-30

## 配置

用户提供的 iFinD MCP 配置已从附件解析，并转换为本地 CLI 可用格式：

- 配置路径：`~/.config/ifind/mcp_config.json`
- 文件权限：`600`
- 粘贴配置中包含的服务数量：7
- token 内容没有写入项目源码。

获得网络授权后，内置 iFinD CLI 已成功列出 `fund` MCP 服务工具。

## 已提取数据

官方 ETF 份额变化数据通过以下方式提取：

- MCP 服务：`fund`
- MCP 工具：`get_fund_ownership`
- 查询模式：精确 ETF 证券代码、日期窗口、每日份额变化表
- 脚本：`scripts/extract_mcp_share_data.py`

命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/extract_mcp_share_data.py --start 2026-06-22 --end 2026-06-30
```

输出：

- Parquet：`data/raw/etf_mcp_share_changes_recent.parquet`
- 原始 MCP 响应：`data/raw/mcp_share_raw/*.json`
- 行数：156
- 标的数量：19
- 缺失标的：无

字段：

- `symbol`
- `name`
- `date`
- `exchange_share_change`
- `listed_trading_shares`
- `source`

重要解释：

- `exchange_share_change` 是可用的官方每日份额变化字段。
- `listed_trading_shares` 在很多响应中更像静态上市流通份额字段，在进一步验证前不应直接当作当前 ETF 总份额。

## 覆盖情况

大部分 ETF 返回了 `2026-06-22` 至 `2026-06-30` 的每日记录。两只 ETF（`159995.SZ`、`510300.SH`）只返回 `2026-06-22` 的单日记录；解析器已能在表格本身没有日期列时，从 MCP 指标参数块读取日期。

## 验证

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

结果：

- 单元测试：12 个通过

与 HTTP 推导份额变化的重叠样本检查：

- 重叠行数：130
- 有效比较行数：114
- 覆盖标的数：18
- MCP `exchange_share_change` 与 HTTP 推导份额变化的相关系数：1.0

这说明至少在重叠样本内，HTTP 推导的 `shares_outstanding` 变化与 MCP 官方份额变化字段完全一致。因此，全样本 HTTP 推导资金流因子的可信度明显提高，但仍建议继续做更长历史窗口的 MCP 抽样验证。

## 下一步

把 MCP 份额变化验证扩展到更多历史窗口，然后二选一：

- 使用滚动日期窗口扩展 MCP 提取。
- 找到精确的 iFinD HTTP/date-sequence 长历史官方 ETF 份额变化指标。

## 年度六月窗口扩展

验证扩展到五个年度六月窗口：

- `2022-06-22` 至 `2022-06-30`
- `2023-06-21` 至 `2023-06-30`
- `2024-06-21` 至 `2024-06-28`
- `2025-06-23` 至 `2025-06-30`
- `2026-06-22` 至 `2026-06-30`

输出文件：

- `data/raw/etf_mcp_share_changes_annual_june.parquet`
- `data/raw/mcp_share_raw_annual_june/*.json`
- `data/processed/mcp_share_validation/annual_june_overlap_details.parquet`
- `data/processed/mcp_share_validation/annual_june_summary.json`

汇总：

- MCP 行数：782
- MCP 标的数：19
- HTTP/MCP 重叠行数：624
- 有效比较行数：554
- 有效比较标的数：19
- MCP 官方份额变化与 HTTP 推导份额变化整体相关系数：0.9994
- 平均绝对差异：约 90 万份

分窗口结果：

| 窗口 | 行数 | 标的数 | 相关系数 | 最大绝对差异 |
|---|---:|---:|---:|---:|
| 2022-06 | 127 | 19 | 1.0000 | 约 0 |
| 2023-06 | 94 | 19 | 1.0000 | 约 0 |
| 2024-06 | 114 | 19 | 0.9962 | 1.22 亿份 |
| 2025-06 | 93 | 18 | 1.0000 | 约 0 |
| 2026-06 | 126 | 18 | 1.0000 | 约 0 |

唯一明显差异集中在 2024-06-24 和 2024-06-25 附近。该处 MCP 的“当期份额变化”和 HTTP 推导的每日变化对部分 ETF 似乎存在一个交易日的归因差异。除这一局部日期问题外，两类数据源基本完全一致。
