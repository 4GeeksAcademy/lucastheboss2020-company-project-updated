from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from scripts.train_sales_forecast import (
    build_training_matrix,
    context_pattern_diagnostics,
    evaluate_forecast,
    forecast_recursively,
    load_sales_data,
    seasonal_naive_forecast,
    run_forecast,
    split_sales_data,
    validate_sales_data,
)
from scripts.evaluate_sales_forecast import (
    chronological_folds,
    evaluate_temporal_cv,
    run_evaluation,
)


def make_sales_data() -> pd.DataFrame:
    months = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
    month_index = np.arange(len(months))
    seasonality = np.where(months.month == 2, 0.88, 1.0)
    seasonality = np.where(months.month >= 11, 1.3, seasonality)
    revenue = (100_000 + month_index * 1_000) * seasonality
    shipments = 5_000 + month_index * 10
    return pd.DataFrame(
        {
            "month": months,
            "revenue_eur": revenue,
            "shipments_processed": shipments,
            "avg_revenue_per_shipment_eur": revenue / shipments,
            "market": "consolidated",
        }
    )


class ConstantEstimator:
    def predict(self, features: np.ndarray) -> np.ndarray:
        return np.full(len(features), 1.05)


class ConstantForest:
    estimators_ = [ConstantEstimator() for _ in range(5)]


def test_split_uses_first_8_years_for_training_and_last_2_for_test() -> None:
    data = validate_sales_data(make_sales_data())
    train, test = split_sales_data(data)

    assert len(train) == 96
    assert len(test) == 24
    assert train["month"].iloc[0] == pd.Timestamp("2016-01-01")
    assert train["month"].iloc[-1] == pd.Timestamp("2023-12-01")
    assert test["month"].iloc[0] == pd.Timestamp("2024-01-01")
    assert test["month"].iloc[-1] == pd.Timestamp("2025-12-01")


def test_validation_rejects_a_missing_month() -> None:
    data = make_sales_data().drop(index=30)

    with pytest.raises(ValueError, match="missing="):
        validate_sales_data(data)


def test_validation_rejects_extra_columns_and_market_rows() -> None:
    data = make_sales_data()
    data["extra"] = 1
    with pytest.raises(ValueError, match="exactly"):
        validate_sales_data(data)

    data = make_sales_data()
    data.loc[0, "market"] = "us"
    with pytest.raises(ValueError, match="only consolidated"):
        validate_sales_data(data)


def test_current_target_does_not_leak_into_its_features() -> None:
    data = validate_sales_data(make_sales_data())
    train, _ = split_sales_data(data)
    features_before, targets_before = build_training_matrix(train)
    target_month = pd.Timestamp("2022-06-01")

    changed_train = train.copy()
    changed_train.loc[changed_train["month"] == target_month, "revenue_eur"] *= 1.5
    features_after, targets_after = build_training_matrix(changed_train)

    assert_series_equal(features_before.loc[target_month], features_after.loc[target_month])
    assert targets_before.loc[target_month] != targets_after.loc[target_month]


def test_same_month_shipments_and_unit_price_are_not_features() -> None:
    data = validate_sales_data(make_sales_data())
    train, _ = split_sales_data(data)
    features_before, _ = build_training_matrix(train)

    changed = train.copy()
    changed["shipments_processed"] *= 3
    changed["avg_revenue_per_shipment_eur"] *= 0.4
    features_after, _ = build_training_matrix(changed)

    assert_frame_equal(features_before, features_after)


def test_recursive_forecast_returns_positive_values_and_a_range() -> None:
    data = validate_sales_data(make_sales_data())
    train, test = split_sales_data(data)

    forecast = forecast_recursively(ConstantForest(), train, test["month"])

    assert len(forecast) == 24
    assert np.isfinite(forecast["predicted_revenue_eur"]).all()
    assert (forecast["predicted_revenue_eur"] > 0).all()
    assert (forecast["tree_p10_revenue_eur"] <= forecast["predicted_revenue_eur"]).all()
    assert (forecast["predicted_revenue_eur"] <= forecast["tree_p90_revenue_eur"]).all()


def test_fixed_origin_forecasts_ignore_holdout_actual_values() -> None:
    data = validate_sales_data(make_sales_data())
    train, test = split_sales_data(data)
    changed_test = test.copy()
    changed_test["revenue_eur"] *= 4

    forecast = forecast_recursively(ConstantForest(), train, test["month"])
    changed_forecast = forecast_recursively(ConstantForest(), train, changed_test["month"])
    baseline = seasonal_naive_forecast(train, test["month"])
    changed_baseline = seasonal_naive_forecast(train, changed_test["month"])

    assert_frame_equal(forecast, changed_forecast)
    assert_frame_equal(baseline, changed_baseline)


def test_perfect_forecast_metrics_are_consistent() -> None:
    data = validate_sales_data(make_sales_data())
    train, test = split_sales_data(data)
    forecast = pd.DataFrame(
        {
            "predicted_revenue_eur": test["revenue_eur"],
        }
    )

    baseline = pd.DataFrame({"seasonal_naive_revenue_eur": test["revenue_eur"]})
    metrics = evaluate_forecast(train, test, forecast, baseline)

    assert metrics["random_forest"]["mse_eur_squared"] == pytest.approx(0.0)
    assert metrics["random_forest"]["normalized_gini"] == pytest.approx(1.0)
    assert metrics["random_forest"]["r2_score"] == pytest.approx(1.0)
    assert metrics["psi_revenue_distribution_train_vs_test"] >= 0.0
    assert metrics["psi_market_mix"] is None
    assert metrics["k2_score"] is None


def test_original_source_matches_documented_growth_and_seasonality() -> None:
    data = load_sales_data()
    diagnostics = context_pattern_diagnostics(data)
    seasonal = diagnostics["within_year_seasonality_pct_by_month"]

    assert len(data) == 120
    assert diagnostics["max_deviation_from_alternating_9_3_pct_points"] <= 1.2
    assert -17.0 <= seasonal["2"] <= -10.0
    assert 25.0 <= seasonal["11"] <= 35.0
    assert 23.0 <= seasonal["12"] <= 35.0
    assert all(abs(seasonal[str(month)]) <= 5.5 for month in range(1, 13) if month not in {2, 11, 12})


def test_training_run_writes_model_metrics_predictions_and_plot(tmp_path: Path) -> None:
    input_path = tmp_path / "synthetic_sales.csv"
    output_dir = tmp_path / "forecast-output"
    make_sales_data().to_csv(input_path, index=False)

    metrics = run_forecast(input_path, output_dir)

    assert metrics["random_forest"]["mse_eur_squared"] >= 0.0
    predictions = pd.read_csv(output_dir / "sales_forecast_test.csv")
    assert len(predictions) == 24
    assert "seasonal_naive_revenue_eur" in predictions.columns
    assert (output_dir / "sales_forecast_model.joblib").is_file()
    assert (output_dir / "sales_forecast_metrics.json").is_file()
    assert (output_dir / "sales_forecast.png").stat().st_size > 0


def test_temporal_folds_are_ordered_non_overlapping_and_five_fold() -> None:
    data = validate_sales_data(make_sales_data())
    training, final_test = split_sales_data(data)

    folds = chronological_folds(training)

    assert len(folds) == 5
    assert final_test["month"].min() == pd.Timestamp("2024-01-01")
    for fold_number, (fold_train, fold_validation) in enumerate(folds):
        assert fold_train["month"].max() < fold_validation["month"].min()
        assert len(fold_validation) == 8
        assert fold_train["month"].is_monotonic_increasing
        assert fold_validation["month"].is_monotonic_increasing
        if fold_number:
            assert folds[fold_number - 1][1]["month"].max() < fold_validation["month"].min()


def test_temporal_cv_reports_fold_mean_and_standard_deviation() -> None:
    data = validate_sales_data(make_sales_data())
    training, _ = split_sales_data(data)

    folds, summary = evaluate_temporal_cv(training, n_estimators=8)

    assert len(folds) == 5
    for metric in ("training_mae_eur", "training_rmse_eur", "validation_mae_eur", "validation_rmse_eur"):
        assert summary[metric]["mean"] >= 0.0
        assert summary[metric]["std"] >= 0.0
    assert all(fold["training_end"] < fold["validation_start"] for fold in folds)


def test_cv_first_fold_training_metrics_ignore_validation_actuals() -> None:
    data = validate_sales_data(make_sales_data())
    training, _ = split_sales_data(data)
    first_fold_train, first_fold_validation = chronological_folds(training)[0]
    changed = training.copy()
    validation_months = set(first_fold_validation["month"])
    mask = changed["month"].isin(validation_months)
    changed.loc[mask, "revenue_eur"] *= 3

    original_folds, _ = evaluate_temporal_cv(training, n_estimators=8)
    changed_folds, _ = evaluate_temporal_cv(changed, n_estimators=8)

    assert first_fold_train["month"].max() < first_fold_validation["month"].min()
    assert original_folds[0]["training_mae_eur"] == pytest.approx(
        changed_folds[0]["training_mae_eur"]
    )
    assert original_folds[0]["training_rmse_eur"] == pytest.approx(
        changed_folds[0]["training_rmse_eur"]
    )
    assert original_folds[0]["validation_mae_eur"] != pytest.approx(
        changed_folds[0]["validation_mae_eur"]
    )


def test_evaluation_writes_fixed_origin_curve_and_report(tmp_path: Path) -> None:
    input_path = tmp_path / "synthetic_sales.csv"
    output_dir = tmp_path / "evaluation"
    make_sales_data().to_csv(input_path, index=False)

    folds, summary, curve = run_evaluation(input_path, output_dir, n_estimators=8)

    report = (output_dir / "evaluation_report.md").read_text()
    assert len(folds) == 5
    assert summary["validation_rmse_eur"]["mean"] >= 0.0
    assert [point["training_months"] for point in curve] == [36, 48, 60, 72, 84]
    assert "fixed-origin" in report.lower()
    assert "underfitting" in report.lower()
    assert "overfitting" in report.lower()
    assert (output_dir / "learning_curve.png").stat().st_size > 0
    assert len(pd.read_csv(output_dir / "temporal_cv_folds.csv")) == 5
