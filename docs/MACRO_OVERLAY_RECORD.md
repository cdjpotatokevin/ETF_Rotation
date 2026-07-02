# Macro Risk Overlay Record

Date: 2026-07-02

## Objective

Rework the macro module from a weekly cross-sectional ranking factor into a low-frequency risk/position overlay.

The overlay does not change ETF selection. It only scales the total exposure of the current primary candidate:

- Candidate: `m_1_3_6_top3_min0p6`
- Base selection: weekly Top 3 momentum
- Benchmark: `510300.SH`
- Macro data: iFinD EDB

## Implemented Components

New code:

- `src/etf_rotation/backtest/macro_overlay.py`
- `scripts/evaluate_macro_overlay.py`
- `tests/test_macro_overlay.py`

Output:

- `data/processed/macro_overlay/macro_overlay_grid.parquet`
- `data/processed/macro_overlay/macro_overlay_grid.csv`
- `data/processed/macro_overlay/macro_overlay_summary.json`
- `data/processed/macro_overlay/best_macro_overlay_curve.parquet`
- `data/processed/macro_overlay/best_macro_overlay_weights.parquet`
- `data/processed/macro_overlay/best_macro_overlay_signal.parquet`

## Method

The macro overlay uses the same macro components as the previous macro factor, but applies them only to total exposure.

Risk score:

- Higher when growth and liquidity are weak.
- Higher when inflation and risk-off pressure are high.
- Macro dates are shifted by `10` calendar days before becoming effective to reduce look-ahead risk.

Default grid:

- Medium-risk thresholds: `0.35`, `0.50`, `0.75`
- High-risk thresholds: `0.75`, `0.85`, `1.00`, `1.25`, `1.50`
- Medium-risk exposure: `90%`, `75%`
- High-risk exposure: `75%`, `50%`

## Best Overlay

Best key:

- `med0p75_high1p5_me0p9_he0p75_lag10`

Configuration:

- Medium-risk threshold: `0.75`
- High-risk threshold: `1.50`
- Medium-risk exposure: `90%`
- High-risk exposure: `75%`
- Macro release lag: `10` days

Average target exposure:

- `97.10%`

Risk days:

- High-risk days: `68`
- Medium-risk days: `181`

## Full-Sample Comparison

| Metric | Base Candidate | Macro Overlay |
|---|---:|---:|
| Total return | 94.08% | 91.43% |
| Annual return | 14.80% | 14.47% |
| Annual volatility | 19.44% | 19.25% |
| Sharpe | 0.76 | 0.75 |
| Max drawdown | -17.02% | -17.02% |
| Excess return | 98.59% | 95.94% |
| Information ratio | 1.14 | 1.12 |
| Average turnover | 5.92% | 5.89% |

Interpretation:

- The overlay does not improve full-sample max drawdown.
- It slightly reduces return and volatility.
- It preserves most of the primary candidate's return profile, unlike the previous weekly macro-ranking factor.

## Walk-Forward Result

| Test Period | Test Return | Sharpe | Max Drawdown | Excess Return |
|---|---:|---:|---:|---:|
| 2022 | -12.97% | -0.79 | -15.04% | 8.11% |
| 2023 | -0.14% | -0.01 | -11.77% | 11.25% |
| 2024 | 30.09% | 1.27 | -13.95% | 13.62% |
| 2025 | 28.82% | 1.53 | -12.35% | 7.23% |
| 2026H1 | 28.67% | 2.79 | -13.39% | 25.05% |

Compared with the base candidate:

- 2025 max drawdown improved from about `-14.05%` to `-12.35%`.
- 2026H1 max drawdown improved slightly from about `-13.47%` to `-13.39%`.
- 2022 max drawdown worsened from about `-14.48%` to `-15.04%`.

## Recommendation

Keep this overlay as an optional defensive branch, not as the primary baseline.

Reason:

- It is much better behaved than using macro as a weekly ranking factor.
- It can help in some periods, especially 2025.
- It has not yet proven enough full-sample drawdown improvement to justify replacing the primary candidate.

Next research:

- Test overlay only when portfolio drawdown/volatility confirms macro risk.
- Test a monthly-only execution schedule for exposure changes.
- Add market breadth or benchmark trend to reduce false macro de-risking.

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/evaluate_macro_overlay.py
```

Result:

- Unit tests: 36 passed
- Macro overlay evaluation completed on real iFinD ETF and macro data.
