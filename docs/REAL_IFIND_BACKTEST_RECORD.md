# Real iFinD Backtest Record

Date: 2026-06-30

## User Decision

Benchmark confirmed as `510300.SH` 沪深300ETF.

## Real Data Collection

Source:

- iFinD HTTP API
- Endpoint: `cmd_history_quotation`
- Provider implementation: `src/etf_rotation/data/ifind_http.py`
- Stored file: `data/raw/etf_daily.parquet`

Requested range:

- 2021-01-01 to 2026-06-30

Actual returned range:

- 2021-06-30 to 2026-06-30

Coverage:

- Rows: 22,855
- Symbols: 19
- Source label: `ifind_http`
- Most ETFs have 1,211 observations.
- `159768.SZ` starts on 2022-02-16 due to later available history.

Fields collected:

- Open, high, low, close
- Volume, amount, turnover ratio
- NAV
- Premium ratio

Updated MCP status:

- The iFinD MCP authorization has been configured locally at `~/.config/ifind/mcp_config.json`.
- Official recent ETF share-flow data has been extracted to `data/raw/etf_mcp_share_changes_recent.parquet`.
- The MCP output currently covers 19 ETF symbols, 156 rows, and the window 2026-06-22 to 2026-06-30.
- The usable official flow field is `exchange_share_change` (`当期场内流通份额变化`).
- An overlap check found 114 valid comparisons between MCP official share changes and HTTP-derived share changes, with correlation of 1.0.
- The validation was extended to five annual June windows from 2022 through 2026. The expanded sample has 782 MCP rows and 554 valid HTTP/MCP comparisons, with overall correlation of 0.9994.

Current limitation:

- HTTP historical quotation does not directly return official daily ETF share totals.
- The full-period backtest still uses `shares_outstanding` estimated from `volume / (turnoverRatio / 100)`.
- MCP validation indicates this derived series matches official share-change data over the checked dates, except for a small cluster around 2024-06-24/25 that appears to be a one-trading-day attribution issue.
- MCP natural-language responses are still not ideal for 5-year daily bulk extraction, so we should continue using HTTP for full-period history and MCP for targeted validation unless a precise long-history share indicator is found.

## Factor IC Results

Forward return horizon: 21 trading days.

| Factor | Mean IC | IC IR | Positive Ratio | Observations |
|---|---:|---:|---:|---:|
| Momentum | -0.0113 | -0.0317 | 48.21% | 1,064 |
| Fund flow | -0.0028 | -0.0101 | 52.17% | 1,127 |
| Crowding | 0.0367 | 0.1350 | 54.17% | 1,128 |
| Baseline score | 0.0044 | 0.0144 | 52.48% | 1,128 |

Interpretation:

- The current baseline signal is weak but slightly positive overall.
- Crowding is the only clearly positive contributor in this initial real-data test.
- Momentum is negative under the current 1M/3M/6M weighting and volatility penalty.
- Fund flow is now supported by strong MCP spot validation, but still needs longer-window validation before it is treated as a final official-flow factor.

## Backtest Results

Backtest design:

- Weekly Friday rebalance
- Select top 5 ETFs by baseline score
- Equal weight, max 25% per ETF
- Transaction cost: 5 bps on one-way turnover
- Benchmark: `510300.SH`

Output files:

- Factor scores: `data/factors/baseline_scores.parquet`
- Factor IC: `data/factors/baseline_factor_ic.parquet`
- Backtest curve: `data/processed/baseline_backtest_curve.parquet`
- Backtest weights: `data/processed/baseline_backtest_weights.parquet`
- Backtest metrics: `data/processed/baseline_backtest_metrics.json`

Metrics:

- Total return: 23.18%
- Annual return: 4.43%
- Annual volatility: 22.32%
- Sharpe: 0.20
- Max drawdown: -33.16%
- Benchmark total return: -4.51%
- Excess total return: 27.69%
- Information ratio: 0.51
- Average daily turnover: 10.55%

Latest rebalance holdings shown in the output:

| Date | Symbol | Weight |
|---|---:|---:|
| 2026-06-26 | 510500.SH | 20% |
| 2026-06-26 | 159915.SZ | 20% |
| 2026-06-26 | 159949.SZ | 20% |
| 2026-06-26 | 159995.SZ | 20% |
| 2026-06-26 | 515000.SH | 20% |

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.validate
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.backtest
```

Results:

- Unit tests: 10 passed
- Data validation: ok
- Backtest: completed

Environment note:

- `pyarrow` prints sandbox `sysctlbyname` CPU-probing warnings in this Codex environment. Parquet read/write and all validation steps completed successfully.

## Recommended Next Work

1. Re-tune the baseline signal: reduce or invert the current momentum component and test crowding-dominant variants.
2. Extend official MCP share-flow extraction to longer rolling windows or locate the exact HTTP/date-sequence indicator for long ETF share history.
3. Add valuation, analyst-consensus prosperity, and macro-resonance factors before treating the strategy as research-complete.
