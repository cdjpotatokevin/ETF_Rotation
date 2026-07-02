# Phase 2 Record: Baseline Factors and Backtest

Date: 2026-06-30

## Scope

This phase adds a runnable baseline factor and backtest layer on top of the Phase 1 normalized ETF daily table.

Implemented baseline factors:

- Momentum: 1M, 3M, and 6M returns with a 3M volatility penalty.
- Fund flow: 1M and 3M percentage changes in ETF shares outstanding.
- Crowding: inverse 1M-vs-3M turnover and amount heat.

Pending factors:

- Valuation
- Prosperity / analyst consensus
- Macro resonance

These pending factors require real iFinD sector, financial, and macro data before they can be validated honestly.

## Implemented Files

- `src/etf_rotation/factors/common.py`
- `src/etf_rotation/factors/momentum.py`
- `src/etf_rotation/factors/fund_flow.py`
- `src/etf_rotation/factors/crowding.py`
- `src/etf_rotation/factors/scoring.py`
- `src/etf_rotation/backtest/engine.py`
- `src/etf_rotation/backtest/pipeline.py`
- `src/etf_rotation/cli/backtest.py`
- `tests/test_factors.py`
- `tests/test_backtest.py`

## Backtest Design

- Frequency: weekly Friday rebalance
- Selection: top 5 ETFs by baseline score
- Weighting: equal weight with max single weight of 25%
- Transaction cost: 5 bps on one-way turnover
- Benchmark: `510300.SH` by default

The benchmark default is an implementation placeholder and should be confirmed before real performance analysis.

## Validation Results

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m etf_rotation.cli.backtest
```

Results:

- Unit tests: 8 passed
- Factor output: `data/factors/baseline_scores.parquet`
- Backtest curve: `data/processed/baseline_backtest_curve.parquet`
- Backtest weights: `data/processed/baseline_backtest_weights.parquet`
- Backtest metrics: `data/processed/baseline_backtest_metrics.json`

Synthetic-data metrics from the smoke test:

- Total return: 132.94%
- Annual return: 16.03%
- Annual volatility: 11.03%
- Sharpe: 1.45
- Max drawdown: -12.40%
- Benchmark total return: -0.42%
- Excess total return: 133.36%
- Information ratio: 0.39
- Average daily turnover: 11.63%

These numbers are generated from deterministic synthetic data and are not investment evidence.

## Next Step

Real iFinD ETF historical data has been connected through HTTP API. The next engineering step is to extend the factor set with:

1. Sector valuation and analyst consensus fields.
2. Macro series such as PMI, CPI, PPI, M2, social financing, and interest rates.
3. Official ETF share series through MCP once `IFIND_AUTH_TOKEN` is configured locally.

See `REAL_IFIND_BACKTEST_RECORD.md` for the real-data run.
