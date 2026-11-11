# TrackFlow Regression Model Evaluation

## Scope and method

- Model: existing fixed-seed Random Forest regressor (`random_state=42`); no hyperparameter search was performed.
- Evaluation data: only the 2016–2023 training period is used here. The 2024–2025 final test set is excluded from folds and the learning curve.
- Temporal cross-validation: expanding `TimeSeriesSplit`, 5 folds, 8-month validation windows. Each fold fits features on its training slice only and predicts its validation window recursively from that origin.
- Learning curve: one fixed validation horizon (2023-01–2023-12), with trailing training histories of 36, 48, 60, 72, 84 months, each ending in 2022-12. This isolates training-size changes from changes in validation dates.
- The 24-month lag/rolling warmup leaves fewer target rows than calendar months in each training window; the count is shown in both result tables.

## Cross-validation metrics

Fold metrics are calculated in EUR. Mean and sample standard deviation (`ddof=1`) across folds:

| Metric | Mean (EUR) | Std dev (EUR) |
| --- | ---: | ---: |
| Training MAE | 14,759.78 | 1,680.28 |
| Validation MAE | 40,392.79 | 13,066.22 |
| Training RMSE | 19,212.41 | 2,142.01 |
| Validation RMSE | 47,606.76 | 12,700.57 |
| Seasonal-naive validation MAE | 75,745.55 | 31,658.39 |
| Seasonal-naive validation RMSE | 85,314.92 | 30,084.06 |

Per-fold results:

| Fold | Training period | Validation period | Train MAE | Validation MAE | Train RMSE | Validation RMSE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | 2016-01–2020-08 (56; 32 targets) | 2020-09–2021-04 (8) | 11,805.22 | 48,501.25 | 15,431.43 | 52,967.51 |
| 2 | 2016-01–2021-04 (64; 40 targets) | 2021-05–2021-12 (8) | 15,571.40 | 31,401.38 | 20,312.68 | 39,157.87 |
| 3 | 2016-01–2021-12 (72; 48 targets) | 2022-01–2022-08 (8) | 15,217.41 | 40,661.27 | 19,787.18 | 51,342.92 |
| 4 | 2016-01–2022-08 (80; 56 targets) | 2022-09–2023-04 (8) | 15,973.64 | 24,328.54 | 20,651.77 | 30,989.68 |
| 5 | 2016-01–2023-04 (88; 64 targets) | 2023-05–2023-12 (8) | 15,231.25 | 57,071.52 | 19,879.01 | 63,575.80 |

## Learning curve

See `data/eval/learning_curve.png`. The two panels show MAE and RMSE for the fixed 2023 horizon. The dashed line is a seasonal-naive baseline that repeats the final 12 training months; all its predictions are also fixed-origin.

| Training months | Usable training targets | Train MAE | Validation MAE | Train RMSE | Validation RMSE | Seasonal-naive RMSE |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 36 | 12 | 21,189.37 | 83,938.60 | 28,150.52 | 97,322.89 | 118,540.79 |
| 48 | 24 | 22,406.03 | 46,031.88 | 28,093.61 | 54,242.60 | 118,540.79 |
| 60 | 36 | 20,200.53 | 44,810.95 | 24,938.32 | 52,111.43 | 118,540.79 |
| 72 | 48 | 17,241.00 | 37,769.35 | 21,477.90 | 44,396.02 | 118,540.79 |
| 84 | 60 | 15,517.31 | 42,473.03 | 20,321.47 | 48,881.65 | 118,540.79 |

## Diagnosis and corrective action

**Classification: Overfitting.** At the largest training history, the validation RMSE is 48,881.65 EUR and the training/validation RMSE gap is 58.4%. Validation RMSE changes by 49.8% between the smallest and largest histories. The same-horizon seasonal-naive RMSE is 118,540.79 EUR.

**Action:** The largest-history validation RMSE remains at least 20% above training RMSE. First constrain tree complexity with a larger min_samples_leaf or max_depth, then compare the same folds.

This diagnosis uses explicit heuristics: a gap of at least 20% indicates overfitting; otherwise, validation RMSE at or above the seasonal-naive RMSE indicates underfitting; a smaller gap with lower validation error than the baseline is classified as well fitted. Fold-to-fold standard deviations above describe temporal stability; they do not prove causal business costs.

## Metric choice and business-cost limitation

MAE is the primary stakeholder-facing measure because it is the average absolute euro error and is easy to interpret. RMSE is reported alongside it because squaring errors gives large misses more weight, which is relevant to seasonal peaks. The TrackFlow briefing does not specify whether over- or under-forecasting is more costly, so no asymmetric penalty or claim about the more expensive direction is made. The final holdout metrics remain in `reports/sales-forecasting/sales_forecast_metrics.json`; this evaluation does not change or tune against the final test period.
