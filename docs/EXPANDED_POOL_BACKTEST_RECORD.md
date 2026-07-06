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

新增测试：

- `tests/test_expanded_pool_backtest.py`
- `tests/test_config.py` 中增加扩展池配置校验

扩展池包含 29 只 ETF：

- 原始 19 只 ETF
- 新增 10 只 A 股股票 ETF：`588000.SH`、`512800.SH`、`512690.SH`、`515030.SH`、`515790.SH`、`159819.SZ`、`512980.SH`、`516020.SH`、`159611.SZ`、`159865.SZ`

## 当前数据状态

新增 10 只 ETF 的代码此前已通过 iFinD MCP `fund.get_fund_profile` 做过识别校验，均可返回基金资料。

但本次真实历史日线数据接入未完成：

- iFinD HTTP 历史行情接口需要 `IFIND_REFRESH_TOKEN`，当前 shell 环境未配置。
- iFinD MCP `fund.get_fund_market_performance` 尝试查询历史日频数据时返回“用户使用工具已超限”。

因此脚本已主动中止扩展池回测，没有生成容易误读的扩展池绩效结果。

数据可用性文件：

- `data/processed/expanded_a_share_pool/data_availability.json`

当前缺失历史行情的新增 ETF：

| ETF代码 | 名称 |
|---|---|
| `588000.SH` | 科创50ETF |
| `512800.SH` | 银行ETF |
| `512690.SH` | 酒ETF |
| `515030.SH` | 新能源车ETF |
| `515790.SH` | 光伏ETF |
| `159819.SZ` | 人工智能ETF |
| `512980.SH` | 传媒ETF |
| `516020.SH` | 化工ETF |
| `159611.SZ` | 电力ETF |
| `159865.SZ` | 养殖ETF |

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

## 风控处理

脚本默认要求扩展池 29 只 ETF 都有历史行情。如果新增 ETF 数据缺失，会中止并输出缺失代码，不运行回测。

只有显式传入 `--allow-incomplete` 时，脚本才允许在数据不完整的情况下运行。这只适合调试，不适合正式研究结论。

## 下一步

等待 iFinD HTTP 刷新令牌可用，或等待 MCP 使用额度恢复后，重新获取新增 10 只 ETF 的历史日线数据，再运行正式扩展池回测。
