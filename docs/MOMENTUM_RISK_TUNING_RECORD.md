# Momentum and Risk-Control Tuning Record

Date: 2026-07-01

## Objective

Continue from the previous finding that high momentum exposure performed best in the 2025-2026 test period, but improve robustness by testing:

- Alternative momentum windows
- Trend filters
- Top-N concentration
- Minimum score thresholds
- Portfolio-level stop loss
- Volatility target scaling

Benchmark remains `510300.SH` 沪深300ETF.

## Implemented Components

New code:

- `src/etf_rotation/factors/momentum_variants.py`
- `src/etf_rotation/backtest/risk_control.py`
- `scripts/tune_momentum_risk.py`
- `tests/test_momentum_risk.py`

The backtest engine now also supports:

- `min_score` filtering before ETF selection
- externally supplied risk-adjusted weights through `run_weighted_backtest`

## Core Grid

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/tune_momentum_risk.py --train-end 2024-12-31 --test-start 2025-01-01 --min-scores none,0.60 --target-vols none,0.18 --stop-losses none,0.18 --output-dir data/processed/momentum_risk_tuning_core
```

Outputs:

- `data/processed/momentum_risk_tuning_core/momentum_risk_grid.parquet`
- `data/processed/momentum_risk_tuning_core/momentum_risk_grid.csv`
- `data/processed/momentum_risk_tuning_core/best_momentum_risk.json`
- `data/processed/momentum_risk_tuning_core/best_momentum_risk_curve.parquet`

Grid dimensions:

- Momentum specs: 6
- Top N: 3, 5
- Min score: none, 0.60
- Target vol: none, 0.18
- Stop loss: none, 0.18

## Best Candidate

Best key:

- `m_1_3_6_top3_min0p6_volnone_stopnone`

Configuration:

- Momentum spec: 1M/3M/6M weighted momentum with volatility penalty
- Top N: 3
- Minimum score: 0.60
- Target volatility scaling: none
- Portfolio stop loss: none

Metrics:

| Period | Total Return | Annual Return | Sharpe | Max Drawdown | Excess Return | Information Ratio |
|---|---:|---:|---:|---:|---:|---:|
| Train | 17.90% | 4.99% | 0.28 | -14.48% | 41.38% | 0.98 |
| Test | 70.63% | 45.51% | 2.00 | -14.05% | 42.24% | 1.53 |
| Full | 94.08% | 14.80% | 0.76 | -17.02% | 98.59% | 1.14 |

## Comparison With Prior Candidate

Previous best from factor-weight tuning:

- Pure momentum, Top 5, no score threshold
- Full Sharpe: 0.54
- Full max drawdown: -29.36%
- Full total return: 84.47%

New best candidate:

- Momentum Top 3 with score threshold 0.60
- Full Sharpe: 0.76
- Full max drawdown: -17.02%
- Full total return: 94.08%

Interpretation:

- The score threshold is doing the most useful risk-control work by keeping the strategy out of weak relative-strength names.
- Top 3 concentration improves the signal-to-noise ratio relative to Top 5.
- Explicit stop-loss did not improve the top result because the selected candidate never breached the tested threshold in a useful way.
- Volatility targeting reduced drawdown in some variants but also reduced upside and did not win the objective.

## Strong Alternatives

| Candidate | Full Sharpe | Full Max DD | Test Sharpe | Notes |
|---|---:|---:|---:|---|
| `m_3_6_trend_top3_min0p6_volnone_stopnone` | 0.78 | -16.08% | 2.03 | Best full Sharpe and lower drawdown, slightly lower objective |
| `m_3_6_top3_min0p6_volnone_stopnone` | 0.68 | -20.59% | 2.09 | Strong test period, weaker train drawdown |
| `m_1_3_6_top3_min0p6_vol0p18_stopnone` | 0.77 | -14.35% | 1.94 | Best drawdown control among top candidates |

## Recommendation

Promote the following two candidates for deeper research:

1. Primary branch: `m_1_3_6_top3_min0p6_volnone_stopnone`
2. Defensive branch: `m_3_6_trend_top3_min0p6_volnone_stopnone`

Next tests should focus on:

- Rolling walk-forward splits, not just one train/test split. Completed in `docs/MOMENTUM_CANDIDATE_VALIDATION_RECORD.md`.
- Monthly vs weekly rebalance. Completed in `docs/MOMENTUM_CANDIDATE_VALIDATION_RECORD.md`.
- Transaction-cost sensitivity. Completed in `docs/MOMENTUM_CANDIDATE_VALIDATION_RECORD.md`.
- Combining the momentum threshold with macro/valuation filters once those factors are added

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

Result:

- Unit tests: 25 passed after candidate-validation additions
