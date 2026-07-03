# 第一阶段记录：数据基础设施

日期：2026-06-30

## 范围

本阶段为 ETF 轮动系统建立本地项目基础：

- `config/project.json` 项目配置
- `config/etf_pool.json` ETF 池
- `src/etf_rotation` Python 包
- 数据源抽象和可复现的合成数据源
- iFinD MCP CLI 封装和 iFinD HTTP API 客户端框架
- Parquet 存储工具
- ETF 日线数据校验
- 数据采集与校验 CLI 命令
- 单元测试

## 已实现文件

- `pyproject.toml`
- `README.md`
- `.env.example`
- `.gitignore`
- `config/project.json`
- `config/etf_pool.json`
- `src/etf_rotation/config.py`
- `src/etf_rotation/models.py`
- `src/etf_rotation/storage.py`
- `src/etf_rotation/validation.py`
- `src/etf_rotation/data/synthetic.py`
- `src/etf_rotation/data/ifind_cli.py`
- `src/etf_rotation/data/ifind_http.py`
- `src/etf_rotation/data/pipeline.py`
- `src/etf_rotation/cli/collect.py`
- `src/etf_rotation/cli/validate.py`
- `tests/`

## 验证结果

运行命令：

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.collect --provider synthetic
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.validate
```

结果：

- 单元测试：6 个通过
- 合成数据 Parquet 文件：`data/raw/etf_daily.parquet`
- 行数：27,227
- 标的数量：19
- 日期范围：`2021-01-01` 至 `2026-06-30`
- 校验状态：通过
- 校验错误：无
- 校验警告：无

说明：在 Codex 沙箱环境中，`pyarrow` 会打印 `sysctlbyname` 权限相关的 CPU 探测警告；Parquet 读写和数据校验均已正常完成。

## 数据结构

标准化 ETF 日线表包含：

- `date`
- `symbol`
- `name`
- `bucket`
- `theme`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `amount`
- `turnover`
- `nav`
- `premium_rate`
- `shares_outstanding`
- `source`

## iFinD 接入状态

项目目前包含两个 iFinD 接入点：

- `IFindCliClient`：调用 `ifind-finance-data` 技能中的已认证 iFinD MCP CLI。
- `IFindHttpClient`：从环境变量读取 `IFIND_REFRESH_TOKEN`，调用 iFinD HTTP API。

真实批量采集在后续阶段已经启用，并通过 `cmd_history_quotation` 获取 ETF 历史行情。真实 token 始终保留在项目源码之外。

## 下一步

第二阶段应基于标准化日线 Parquet 表开发因子模块：

1. 使用 1M/3M/6M 收益率和趋势稳定性构建动量因子。
2. 使用 `shares_outstanding` 变化构建资金流因子。
3. 使用换手率和成交额 z-score 构建拥挤度因子。
4. 建立每周调仓基线回测。

基准已由用户确认使用 `510300.SH` 沪深300ETF。
