# ETF Rotation Project Plan

Updated: 2026-07-01

## Confirmed Decisions

- Project path: `/Users/sweethome/Qoder/etf-rotation`
- Storage: local Parquet files
- Research period: 2021-01-01 to 2026-06-30
- ETF pool: default industry plus style universe from the prior plan
- Execution mode: each phase must include a record document and runnable tests

## Phase Roadmap

### Phase 1: Data Infrastructure

Goal: build a reproducible local data layer.

Deliverables:
- ETF universe and project configuration.
- Provider abstraction for synthetic, iFinD MCP CLI, and iFinD HTTP API.
- Parquet storage utilities.
- Data quality checks.
- CLI collection and validation commands.
- Phase record and tests.

Status: completed with synthetic and iFinD HTTP data. Real ETF historical bars were collected through `cmd_history_quotation`.

### Phase 2: Factor Calculation and Backtesting

Goal: implement and validate the six-factor signal framework.

Deliverables:
- Momentum, valuation, prosperity, fund-flow, crowding, and macro-resonance factors.
- Factor normalization and score aggregation.
- Single-factor IC tests.
- Weekly rebalance backtest engine.
- Baseline strategy report.

Status: baseline completed for momentum, fund-flow, crowding, and weekly Top-N rotation using real iFinD ETF data. Macro EDB data and most sector-index daily series have now been collected. A first transparent macro-resonance factor was implemented but failed IC/backtest validation, so it is not promoted to the main strategy. Valuation and prosperity factors remain pending because current sector valuation/consensus queries returned empty tables.

### Phase 3: Portfolio Optimization and Risk Control

Goal: convert scores into implementable portfolios.

Deliverables:
- Risk parity or inverse-volatility allocation.
- Position constraints.
- Stop-loss, drawdown, volatility, and crowding rules.
- Parameter sensitivity analysis.

Status: in progress. Momentum Top3 + score threshold candidate has completed rolling walk-forward, transaction-cost, rebalance-frequency, and liquidity-threshold validation on real iFinD ETF history. A macro risk overlay branch has been implemented and evaluated, but remains optional because full-sample drawdown was not improved.

### Phase 4: Paper Trading and Iteration

Goal: run live signal tracking before real execution.

Deliverables:
- Daily/weekly signal refresh.
- Paper portfolio ledger.
- Drift checks between backtest assumptions and live data.
- Manual confirmation workflow for early live deployment.

## Current Decision Queue

The benchmark decision is complete: use `510300.SH` (沪深300ETF).

Next decision point:
- Keep weekly rebalance as the current primary branch.
- Consider a 50m 20-day average amount filter as the first execution constraint for paper trading readiness.
- Add the defensive `m_3_6_trend_top3_min0p6` branch to the same validation harness.
- Keep macro overlay as an optional defensive branch and improve it with market trend/breadth confirmation.
- Resolve sector valuation/consensus identifiers: exact iFinD sector codes, stock-level aggregation, or temporary postponement.
- Review real estate and technology sector-index proxies, which currently return sparse series.
