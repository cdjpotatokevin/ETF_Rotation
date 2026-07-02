# Macro Factor Record

Date: 2026-07-02

## Objective

Use the newly collected iFinD macro EDB data to implement a first transparent version of the macro-resonance factor.

The goal was not to optimize the signal, but to test whether a simple rule-based macro mapping has standalone predictive value before adding it to the production candidate.

## Implemented Components

New code:

- `src/etf_rotation/factors/macro.py`
- `scripts/evaluate_macro_factor.py`
- `tests/test_macro_factor.py`

Updated:

- `src/etf_rotation/factors/ic.py` now includes `macro_resonance_score` and dynamically detects additional `*_score` columns.

## Factor Logic

The first version uses transparent macro components:

- Growth: PMI, social financing, M2, less 10Y yield pressure
- Inflation: CPI and PPI
- Liquidity: M2 and social financing, less 10Y yield pressure
- Risk-off: weak growth plus yield/inflation pressure

Each macro indicator is standardized by rolling z-score. ETF themes then receive fixed exposures to the macro components, for example:

- Growth and technology themes prefer growth plus liquidity.
- Resource themes prefer inflation.
- Defensive themes prefer risk-off.
- Dividend low-vol prefers risk-off and inflation.

The score is ranked cross-sectionally each day as `macro_resonance_score`.

## Command

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_factor.py
```

Outputs:

- `data/processed/macro_factor/macro_scores.parquet`
- `data/processed/macro_factor/macro_factor_ic.parquet`
- `data/processed/macro_factor/macro_backtest_curve.parquet`
- `data/processed/macro_factor/macro_backtest_weights.parquet`
- `data/processed/macro_factor/macro_factor_metrics.json`

## Result

Macro blend weights tested:

| Factor | Weight |
|---|---:|
| Momentum | 45% |
| Fund flow | 20% |
| Crowding | 20% |
| Macro resonance | 15% |

Backtest result:

| Metric | Value |
|---|---:|
| Total return | 0.05% |
| Annual return | 0.01% |
| Sharpe | 0.00 |
| Max drawdown | -40.53% |
| Benchmark total return | -4.51% |
| Excess total return | 4.56% |
| Information ratio | 0.15 |

IC result:

| Factor | Mean IC | IC IR | Positive Ratio |
|---|---:|---:|---:|
| Macro resonance | -0.0343 | -0.0909 | 47.01% |
| Momentum | -0.0113 | -0.0317 | 48.21% |
| Fund flow | -0.0028 | -0.0101 | 52.17% |
| Crowding | 0.0367 | 0.1350 | 54.17% |
| Macro blend baseline | -0.0107 | -0.0334 | 49.37% |

## Interpretation

The macro data layer is usable, but this first rule-based macro-resonance mapping is not ready for the main strategy.

Important findings:

- The macro factor has negative IC over this ETF pool and sample.
- Adding it at 15% weight materially worsens the baseline backtest profile.
- The result likely reflects lag and regime instability: macro data is monthly/low-frequency, while ETF rotation leadership changes faster in A-share sector/style ETFs.
- A simple static mapping from macro states to themes is too rigid.

## Recommendation

Do not add this macro factor to the primary candidate yet.

Next macro research should test:

- Lower-frequency use: monthly or quarterly risk overlay instead of weekly ranking factor.
- Regime filter: only control equity exposure or defensive tilt, not sector ranking.
- HMM/regime classifier with out-of-sample validation.
- Contrarian macro interpretation as a diagnostic only, not as an immediate production change.

The current primary candidate remains `m_1_3_6_top3_min0p6`.

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_factor.py
```

Result:

- Unit tests: 34 passed
- Macro factor evaluation completed on real iFinD ETF and macro data.
