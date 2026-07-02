# Phase 1 Record: Data Infrastructure

Date: 2026-06-30

## Scope

This phase establishes the local project foundation for the ETF rotation system:

- Project configuration in `config/project.json`
- ETF universe in `config/etf_pool.json`
- Python package under `src/etf_rotation`
- Provider abstraction and deterministic synthetic provider
- iFinD MCP CLI wrapper and HTTP API client shell
- Parquet storage utility
- ETF daily data validation
- Collection and validation CLI commands
- Unit tests

## Implemented Files

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

## Validation Results

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.collect --provider synthetic
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.validate
```

Results:

- Unit tests: 6 passed
- Synthetic Parquet file: `data/raw/etf_daily.parquet`
- Rows: 27,227
- Symbols: 19
- Date range: 2021-01-01 to 2026-06-30
- Validation status: ok
- Validation errors: none
- Validation warnings: none

Note: `pyarrow` prints sandbox CPU-probing warnings about `sysctlbyname` permissions in this Codex environment. Parquet write/read and validation completed successfully.

## Data Schema

The normalized ETF daily table contains:

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

## iFinD Integration Status

The project now contains two integration points:

- `IFindCliClient`: calls the authenticated iFinD MCP CLI from the `ifind-finance-data` skill.
- `IFindHttpClient`: reads `IFIND_REFRESH_TOKEN` from the environment and calls iFinD HTTP API endpoints.

Real batch ingestion is not yet enabled because we still need live sample responses for `cmd_history_quotation` to lock the exact JSON-to-table parser. Tokens must remain outside source code.

## Next Step

Phase 2 should start with factor modules using the normalized daily Parquet table:

1. Momentum factor from 1M/3M/6M returns and trend stability.
2. Fund-flow factor from `shares_outstanding` changes.
3. Crowding factor from turnover and volume z-scores.
4. Baseline weekly rebalance backtest.

Before benchmarking Phase 2, decide whether the primary benchmark should be 沪深300ETF, 沪深300ETF/中证500ETF blend, or another custom benchmark.
