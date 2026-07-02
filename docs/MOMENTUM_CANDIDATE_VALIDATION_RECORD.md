# Momentum Candidate Validation Record

Date: 2026-07-01

## Objective

Validate the fixed candidate selected by the momentum/risk tuning step, without retuning parameters:

- Momentum spec: `m_1_3_6`
- Selection: Top 3
- Minimum score: `0.60`
- Single ETF cap: `25%`
- Rebalance: weekly Friday
- Transaction cost: `5bps`
- Liquidity filter: none in the primary branch; tested separately with 20-day average amount thresholds
- Benchmark: `510300.SH` 沪深300ETF

## Implemented Components

New code:

- `scripts/validate_momentum_candidate.py`
- `tests/test_momentum_candidate_validation.py`

Backtest engine improvement:

- `build_weekly_weights` now returns a stable empty schema when no ETF passes the score threshold. This allows high-threshold strategies to naturally stay in cash instead of failing.

## Command

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/validate_momentum_candidate.py
```

Outputs:

- `data/processed/momentum_candidate_validation/walk_forward.parquet`
- `data/processed/momentum_candidate_validation/walk_forward.csv`
- `data/processed/momentum_candidate_validation/cost_sensitivity.parquet`
- `data/processed/momentum_candidate_validation/cost_sensitivity.csv`
- `data/processed/momentum_candidate_validation/implementation_sensitivity.parquet`
- `data/processed/momentum_candidate_validation/implementation_sensitivity.csv`
- `data/processed/momentum_candidate_validation/candidate_full_curve.parquet`
- `data/processed/momentum_candidate_validation/candidate_full_weights.parquet`
- `data/processed/momentum_candidate_validation/summary.json`

## Full-Sample Result

| Metric | Value |
|---|---:|
| Total return | 94.08% |
| Annual return | 14.80% |
| Annual volatility | 19.44% |
| Sharpe | 0.76 |
| Max drawdown | -17.02% |
| Benchmark total return | -4.51% |
| Excess total return | 98.59% |
| Information ratio | 1.14 |
| Average daily turnover | 5.92% |

## Rolling Walk-Forward Result

Parameters are fixed across all rows. Train windows are recorded for context only; each test row is the next period after the train window.

| Test Period | Test Return | Benchmark Excess | Sharpe | Max Drawdown | Information Ratio |
|---|---:|---:|---:|---:|---:|
| 2022 | -12.77% | 8.31% | -0.76 | -14.48% | 0.68 |
| 2023 | 0.05% | 11.44% | 0.00 | -11.77% | 1.24 |
| 2024 | 29.85% | 13.37% | 1.26 | -13.95% | 1.00 |
| 2025 | 27.33% | 5.74% | 1.39 | -14.05% | 0.52 |
| 2026H1 | 30.40% | 26.78% | 2.95 | -13.47% | 2.84 |

Interpretation:

- The candidate is not solely a 2025-2026 artifact. It has positive excess return in every annual/half-year walk-forward test window.
- 2022 remains a weak absolute-return year, but the strategy still lost much less than the benchmark.
- 2023 was close to flat in absolute terms, while still delivering meaningful benchmark-relative excess.
- Drawdown stayed in a narrow band around 11.8%-14.5% in all test windows.

## Transaction-Cost Sensitivity

| Cost | Total Return | Annual Return | Sharpe | Max Drawdown | Excess Return |
|---:|---:|---:|---:|---:|---:|
| 0bps | 101.16% | 15.65% | 0.81 | -16.85% | 105.67% |
| 5bps | 94.08% | 14.80% | 0.76 | -17.02% | 98.59% |
| 10bps | 87.25% | 13.94% | 0.72 | -17.19% | 91.76% |
| 20bps | 74.30% | 12.26% | 0.63 | -18.76% | 78.81% |
| 50bps | 40.53% | 7.34% | 0.38 | -27.67% | 45.04% |

Interpretation:

- The strategy is robust to moderate costs. At 20bps it still keeps a 74.30% full-sample total return and 78.81% excess return.
- At 50bps the edge is materially compressed, so live implementation should avoid high turnover execution and use realistic ETF liquidity constraints.

## Rebalance and Liquidity Sensitivity

Liquidity filter uses 20-day average amount. The primary branch is weekly Friday rebalance with no liquidity filter.

| Rebalance | Min Avg Amount | Total Return | Sharpe | Max Drawdown | Excess Return | Avg Turnover |
|---|---:|---:|---:|---:|---:|---:|
| Weekly | None | 94.08% | 0.76 | -17.02% | 98.59% | 5.92% |
| Weekly | 50m | 82.92% | 0.65 | -18.98% | 87.43% | 6.17% |
| Weekly | 100m | 67.97% | 0.56 | -26.06% | 72.48% | 5.80% |
| Weekly | 200m | 55.45% | 0.48 | -28.55% | 59.95% | 5.59% |
| Monthly | None | 40.85% | 0.36 | -21.36% | 45.36% | 3.24% |
| Monthly | 50m | 17.15% | 0.16 | -35.52% | 21.66% | 2.99% |
| Monthly | 100m | 4.62% | 0.04 | -40.97% | 9.13% | 3.03% |
| Monthly | 200m | 76.59% | 0.43 | -36.25% | 81.10% | 2.70% |

Interpretation:

- Weekly rebalance remains the primary branch. Monthly rebalance reduces turnover, but the performance sacrifice is too large under the current momentum signal.
- A 50m 20-day average amount filter is still usable if execution discipline is prioritized.
- 100m and 200m weekly filters materially reduce the strategy's edge in this 19-ETF pool.
- Monthly plus high liquidity threshold is unstable: the 200m row recovers total return but with much worse drawdown and lower risk-adjusted performance.

## Recommendation

Keep `m_1_3_6_top3_min0p6` as the primary research branch. The next practical validation steps are:

- Keep weekly rebalance for now.
- Consider a 50m 20-day average amount filter as the first live-execution constraint, but do not make it the research baseline yet.
- Build the defensive branch `m_3_6_trend_top3_min0p6` into the same validation script for side-by-side monitoring.
- Add valuation, prosperity, and macro filters only after their iFinD data sources are wired cleanly.

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/validate_momentum_candidate.py
```

Result:

- Unit tests: 25 passed
- Candidate validation completed on real iFinD ETF historical data.
