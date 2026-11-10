# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._

## Sales Forecasting

Install dependencies and reproduce the tests and real-data run with `uv`:

```bash
uv run --no-project --with-requirements scripts/requirements-sales-forecast.txt --with pytest python -m pytest tests/pipelines/test_sales_forecast.py -q
uv run --no-project --with-requirements scripts/requirements-sales-forecast.txt python scripts/train_sales_forecast.py
```

The original CSV was downloaded without transformation from [the TrackFlow source at commit `2869fa3d9a89b820aab4b8f6adaaadd63d37e530`](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/2869fa3d9a89b820aab4b8f6adaaadd63d37e530/content/contexts/sales-forecasting/trackflow/trackflow_sales.csv). Its SHA-256 is `2b8c782efe182aa001db8044689e3d65e98b2cc17649b598cedb665e7d2f4c33`; `data/raw/trackflow_sales.csv.sha256` records the checksum. Its Git blob ID `66fde90bd2451a7fd8833c3bafccd4e5419398a8` matches the pinned source tree. Validation confirms exactly five ordered columns, 120 consolidated rows from 2016-01 through 2025-12, no missing months, and positive revenue. Only consolidated rows exist, so no market-mix PSI is inferred.

The model is a `RandomForestRegressor` trained with `random_state=42` on the first 96 months (2016-2023); 2024-2025 is held out. With only 96 training targets, a forest is a practical, explainable bagged-tree baseline that needs little tuning. It predicts year-over-year revenue ratios instead of extrapolating raw revenue, using only prior revenue ratios and calendar features. Shipment count and average revenue per shipment are deliberately excluded because same-month values would not be known for a future forecast. Tree models do not require scaling; cyclical calendar features and growth ratios are already bounded and comparable.

Evaluation is **fixed-origin recursive**: all 24 test months are forecast from the 2016-2023 training history, and later horizons use earlier model predictions. No test actual is fed back into a later forecast. This is not a rolling one-step evaluation. The seasonal-naive comparator repeats the last observed 12-month seasonal pattern, also recursively without test actuals.

Reported metrics on the 2024-2025 holdout include:

- **MSE (EUR²)**: mean squared revenue error; **RMSE (EUR)** is its square root, and **RMSE / mean test revenue (%)** scales that error for Finance.
- **Revenue-distribution PSI**: population stability index comparing training and test revenue bins defined from training quantiles. It is not the requested US/Spain volume-mix PSI; that is unavailable because the source has no market-level rows.
- **Normalized regression Gini**: ranking quality of predicted versus actual revenue (1 is perfect ordering; 0 is no ordering lift). It helps assess whether unusual low months are ranked correctly, but does not replace the error magnitude metrics.
- **R²**: coefficient of determination, reported explicitly. Neither the local assignment nor upstream briefing defines **K2 Score**, so K2 is left uncomputed; any interpretation of K2 as R² is unconfirmed.

The plot compares actual revenue, the Random Forest forecast, and seasonal-naive baseline. Its shaded 10th-90th percentile range is the spread of individual forest-tree forecasts, not a calibrated 80% prediction interval; correlated trees can understate uncertainty, especially across a recursive two-year horizon.

The checked-in results below are generated from the pinned source CSV. Tests also use small synthetic in-memory examples for controlled split, leakage, and artifact assertions; synthetic values are never used as TrackFlow evaluation results.

### Pinned source run

| Metric | Random Forest | Seasonal-naive baseline |
| --- | ---: | ---: |
| MSE (EUR²) | 4,473,614,123.78 | 15,355,054,004.48 |
| RMSE (EUR) | 66,885.08 | 123,915.51 |
| RMSE / test mean revenue | 5.15% | 9.54% |
| Normalized regression Gini | 0.8956 | 0.7755 |
| R² | 0.8472 | 0.4754 |

The model's MSE is 70.87% lower than the seasonal-naive comparator on this holdout. Revenue-distribution PSI is 9.3133, indicating a substantial train/test revenue-distribution shift; this is consistent with the increasing revenue trend and is not country-mix PSI. Market-mix PSI is unavailable, and K2 remains uncomputed because neither source defines it.

The test command above completed with **10 passed**. The 10th-90th percentile tree-spread band contains 13 of 24 actual holdout observations (54.17%). That empirical coverage is below its nominal central 80% tree quantile range, confirming it should be interpreted only as model-tree variability—not as a calibrated prediction interval.

The data-pattern audit reports calendar-year revenue growth of 9.58%, 1.82%, 9.42%, 2.92%, 8.03%, 2.80%, 10.12%, 3.99%, and 7.93% for 2017-2025. The maximum deviation from the alternating 9%/3% pattern is 1.18 percentage points. Revenue relative to each year's average is -15.89% in February, +25.28% in November, and +23.96% in December; other months range from -5.05% to -2.17%. The source is preserved as-is; these observed noise-level deviations are documented, not edited out.

Artifacts from the real-data run are under the ignored `reports/sales-forecasting/` directory: `sales_forecast_metrics.json`, `sales_forecast_test.csv`, `sales_forecast.png`, and `sales_forecast_model.joblib`.
