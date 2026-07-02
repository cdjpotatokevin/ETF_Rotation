# Factor Weight Tuning Record

Date: 2026-07-01

## Objective

Retune the three currently available baseline factors using real iFinD ETF data:

- Momentum
- Fund flow
- Crowding

The benchmark remains `510300.SH` 沪深300ETF.

## Method

Script:

- `scripts/tune_factor_weights.py`

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/tune_factor_weights.py --train-end 2024-12-31 --test-start 2025-01-01 --step 0.1
```

Grid:

- Weight step: 0.1
- All non-negative combinations where momentum + fund flow + crowding = 1.0
- 66 combinations

Split:

- Train: data through 2024-12-31
- Test: data from 2025-01-01 onward

Outputs:

- `data/processed/weight_tuning/factor_weight_grid.parquet`
- `data/processed/weight_tuning/factor_weight_grid.csv`
- `data/processed/weight_tuning/best_weights.json`
- `data/processed/weight_tuning/best_weight_backtest_curve.parquet`

## Best Candidate

Best key:

- `m1.0_f0.0_c0.0`

Weights:

- Momentum: 1.0
- Fund flow: 0.0
- Crowding: 0.0

Metrics:

| Period | Total Return | Annual Return | Sharpe | Max Drawdown | Excess Return | Information Ratio |
|---|---:|---:|---:|---:|---:|---:|
| Train | 3.25% | 0.95% | 0.04 | -29.36% | 26.73% | 0.80 |
| Test | 86.89% | 55.11% | 1.96 | -15.68% | 58.50% | 1.62 |
| Full | 84.47% | 13.59% | 0.54 | -29.36% | 88.98% | 1.07 |

## Top Candidates

| Rank | Weights (M/F/C) | Train Sharpe | Test Sharpe | Full Sharpe | Test Excess | Full Excess | Full Max DD |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 1.0 / 0.0 / 0.0 | 0.04 | 1.96 | 0.54 | 58.50% | 88.98% | -29.36% |
| 2 | 0.8 / 0.1 / 0.1 | 0.06 | 1.90 | 0.54 | 53.75% | 87.17% | -30.08% |
| 3 | 0.9 / 0.1 / 0.0 | -0.16 | 2.01 | 0.40 | 60.56% | 62.92% | -37.69% |
| 4 | 0.9 / 0.0 / 0.1 | 0.04 | 1.82 | 0.50 | 50.53% | 81.70% | -32.84% |
| 5 | 0.8 / 0.2 / 0.0 | -0.13 | 1.86 | 0.38 | 52.80% | 59.79% | -37.43% |

## Interpretation

The grid search strongly favors high momentum weights, mainly because momentum performed very well in the 2025-2026 test period.

However, this should not be treated as final proof that a pure momentum strategy is structurally best:

- Train-period Sharpe is only 0.04 for the best candidate.
- The previously computed 21-day cross-sectional IC for momentum is slightly negative.
- The result may reflect a 2025-2026 market regime where growth and technology trends dominated.

Working recommendation:

- Use a momentum-heavy candidate as the next research branch.
- Do not remove crowding yet; test regime-dependent weights and drawdown control first.
- Re-run tuning after adding valuation, analyst-consensus prosperity, and macro-resonance factors.
