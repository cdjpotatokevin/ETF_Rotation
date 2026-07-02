# ETF Rotation

Industry and style ETF rotation research system for A-share ETFs.

## Phase 1 Scope

- Project configuration and ETF universe.
- Data-provider abstraction for iFinD MCP CLI, iFinD HTTP API, and deterministic synthetic data.
- Parquet-first local storage.
- Data quality checks for ETF daily bars.
- CLI commands for collection and validation.
- Phase records under `docs/`.

## Quick Start

Use a Python environment with `pandas`, `numpy`, and `pyarrow`.

```bash
python -m pip install -e ".[dev]"
python -m etf_rotation.cli.collect --provider synthetic
python -m etf_rotation.cli.validate
python -m etf_rotation.cli.backtest
python -m unittest discover -s tests
```

If using iFinD, copy `.env.example` to `.env` locally or export tokens in the shell. Never commit real tokens.

```bash
export IFIND_AUTH_TOKEN="..."
export IFIND_REFRESH_TOKEN="..."
```

Then collect real HTTP historical ETF bars:

```bash
python -m etf_rotation.cli.collect --provider ifind-http
python -m etf_rotation.cli.validate
python -m etf_rotation.cli.backtest
```

Official recent ETF share-flow data can be extracted through MCP after `~/.config/ifind/mcp_config.json` is configured:

```bash
python scripts/extract_mcp_share_data.py --start 2026-06-22 --end 2026-06-30
```

Annual sample windows and factor-weight tuning:

```bash
python scripts/extract_mcp_share_data.py --windows 2022-06-22:2022-06-30,2023-06-21:2023-06-30,2024-06-21:2024-06-28,2025-06-23:2025-06-30,2026-06-22:2026-06-30 --output data/raw/etf_mcp_share_changes_annual_june.parquet --raw-dir data/raw/mcp_share_raw_annual_june
python scripts/tune_factor_weights.py --train-end 2024-12-31 --test-start 2025-01-01 --step 0.1
python scripts/tune_momentum_risk.py --train-end 2024-12-31 --test-start 2025-01-01 --min-scores none,0.60 --target-vols none,0.18 --stop-losses none,0.18 --output-dir data/processed/momentum_risk_tuning_core
python scripts/validate_momentum_candidate.py
python scripts/collect_ifind_research_data.py --datasets macro
python scripts/collect_ifind_research_data.py --datasets sector_index --sector-window-months 3
python scripts/evaluate_macro_factor.py
```

## Decisions Already Applied

- Project directory: `/Users/sweethome/Qoder/etf-rotation`
- Storage: Parquet files
- Backtest data range: 2021-01-01 to 2026-06-30
- ETF universe: default industry plus style pool from the prior plan

## Current Baseline

The current Phase 2 baseline uses three factors available from ETF daily data:

- Momentum: 1M/3M/6M returns minus volatility penalty.
- Fund flow: 1M/3M changes in shares outstanding.
- Crowding: inverse short-term turnover and amount heat.

The baseline backtest rebalances weekly into the top-scoring ETFs with equal weights subject to a single-position cap. See `docs/REAL_IFIND_BACKTEST_RECORD.md` for the current real iFinD run.

## Current Research Candidate

The current primary candidate is `m_1_3_6_top3_min0p6`:

- 1M/3M/6M weighted momentum with volatility penalty.
- Weekly Top 3 ETF rotation.
- Minimum score threshold `0.60`.
- Single ETF cap `25%`, leaving unused capital in cash when fewer names qualify.
- Benchmark: `510300.SH` 沪深300ETF.
- Weekly rebalance remains preferred over monthly in the current validation.
- A 50m 20-day average amount filter is the first execution constraint to consider, but not yet the research baseline.

See `docs/MOMENTUM_CANDIDATE_VALIDATION_RECORD.md` for rolling walk-forward and transaction-cost sensitivity results on real iFinD ETF history.

## Extended Data Status

Macro EDB data and most sector index daily series have been collected through iFinD MCP. The first transparent macro-resonance factor was implemented and tested, but it is not promoted to the main strategy because its IC and backtest contribution were weak. Sector valuation and consensus fields are not yet parsed because the current `sector_data` queries returned empty tables; see `docs/MACRO_SECTOR_DATA_RECORD.md` and `docs/MACRO_FACTOR_RECORD.md` for details.
