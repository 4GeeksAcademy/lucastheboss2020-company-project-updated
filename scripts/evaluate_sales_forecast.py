#!/usr/bin/env python3
"""Evaluate the TrackFlow revenue Random Forest with chronological validation.

Run from the repository root with:
    uv run --no-project --with-requirements scripts/requirements-sales-forecast.txt --with pytest python -m pytest tests/pipelines/test_sales_forecast.py -q
    uv run --no-project --with-requirements scripts/requirements-sales-forecast.txt python scripts/evaluate_sales_forecast.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean, stdev

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from scripts.train_sales_forecast import (
    DEFAULT_INPUT,
    build_training_matrix,
    forecast_recursively,
    load_sales_data,
    seasonal_naive_forecast,
    split_sales_data,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "data" / "eval"
CV_SPLITS = 5
CV_VALIDATION_MONTHS = 8
LEARNING_CURVE_VALIDATION_MONTHS = 12
LEARNING_CURVE_TRAIN_SIZES = (36, 48, 60, 72, 84)


def make_model(n_estimators: int = 400) -> RandomForestRegressor:
    """Use the same fixed-seed Random Forest specification as the forecaster."""
    return RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=2,
        max_features=1.0,
        random_state=42,
        n_jobs=-1,
    )


def chronological_folds(
    training: pd.DataFrame,
    n_splits: int = CV_SPLITS,
    validation_size: int = CV_VALIDATION_MONTHS,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Create expanding chronological folds; every train slice precedes validation."""
    if n_splits < 5:
        raise ValueError("At least five temporal cross-validation folds are required.")
    ordered = training.sort_values("month").reset_index(drop=True)
    if ordered["month"].duplicated().any() or not ordered["month"].is_monotonic_increasing:
        raise ValueError("Cross-validation requires unique, chronologically ordered months.")

    splitter = TimeSeriesSplit(n_splits=n_splits, test_size=validation_size)
    folds = []
    for train_indices, validation_indices in splitter.split(ordered):
        fold_train = ordered.iloc[train_indices].copy().reset_index(drop=True)
        fold_validation = ordered.iloc[validation_indices].copy().reset_index(drop=True)
        if fold_train["month"].max() >= fold_validation["month"].min():
            raise AssertionError("A temporal fold has overlapping or reversed dates.")
        if not pd.date_range(
            fold_validation["month"].iloc[0],
            fold_validation["month"].iloc[-1],
            freq="MS",
        ).equals(pd.DatetimeIndex(fold_validation["month"])):
            raise ValueError("Every validation fold must contain consecutive monthly observations.")
        folds.append((fold_train, fold_validation))
    return folds


def _revenue_predictions_for_training(
    training: pd.DataFrame,
    model: RandomForestRegressor,
    features: pd.DataFrame,
) -> tuple[pd.Series, pd.Series]:
    """Convert fitted growth-ratio predictions to EUR for training metrics."""
    revenue_by_month = training.set_index("month")["revenue_eur"].astype(float)
    target_months = pd.DatetimeIndex(features.index)
    base_months = target_months - pd.DateOffset(years=1)
    base_revenue = revenue_by_month.reindex(base_months).to_numpy(dtype=float)
    actual_revenue = revenue_by_month.reindex(target_months).to_numpy(dtype=float)
    predicted_growth = model.predict(features)
    return pd.Series(actual_revenue), pd.Series(base_revenue * predicted_growth)


def _error_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae_eur": float(mean_absolute_error(actual, predicted)),
        "rmse_eur": float(np.sqrt(mean_squared_error(actual, predicted))),
    }


def _fit_fold_model(
    training: pd.DataFrame,
    n_estimators: int,
) -> tuple[RandomForestRegressor, pd.DataFrame]:
    features, targets = build_training_matrix(training)
    if len(features) == 0:
        raise ValueError("A fold has no usable lagged training examples after feature warmup.")
    model = make_model(n_estimators=n_estimators)
    model.fit(features, targets)
    return model, features


def evaluate_temporal_cv(
    training: pd.DataFrame,
    n_splits: int = CV_SPLITS,
    validation_size: int = CV_VALIDATION_MONTHS,
    n_estimators: int = 400,
) -> tuple[list[dict[str, object]], dict[str, dict[str, float]]]:
    """Evaluate training and recursive validation errors across expanding folds."""
    fold_results = []
    metric_names = (
        "training_mae_eur",
        "training_rmse_eur",
        "validation_mae_eur",
        "validation_rmse_eur",
        "seasonal_naive_mae_eur",
        "seasonal_naive_rmse_eur",
    )
    for fold_number, (fold_train, fold_validation) in enumerate(
        chronological_folds(training, n_splits, validation_size),
        start=1,
    ):
        model, training_features = _fit_fold_model(fold_train, n_estimators)
        train_actual, train_prediction = _revenue_predictions_for_training(
            fold_train,
            model,
            training_features,
        )
        validation_prediction = forecast_recursively(model, fold_train, fold_validation["month"])
        baseline_prediction = seasonal_naive_forecast(fold_train, fold_validation["month"])
        validation_actual = fold_validation["revenue_eur"].astype(float).reset_index(drop=True)

        fold_results.append(
            {
                "fold": fold_number,
                "training_start": fold_train["month"].iloc[0].strftime("%Y-%m"),
                "training_end": fold_train["month"].iloc[-1].strftime("%Y-%m"),
                "training_months": len(fold_train),
                "training_target_months": len(training_features),
                "validation_start": fold_validation["month"].iloc[0].strftime("%Y-%m"),
                "validation_end": fold_validation["month"].iloc[-1].strftime("%Y-%m"),
                "validation_months": len(fold_validation),
                "training_mae_eur": _error_metrics(train_actual, train_prediction)["mae_eur"],
                "training_rmse_eur": _error_metrics(train_actual, train_prediction)["rmse_eur"],
                "validation_mae_eur": _error_metrics(
                    validation_actual,
                    validation_prediction["predicted_revenue_eur"],
                )["mae_eur"],
                "validation_rmse_eur": _error_metrics(
                    validation_actual,
                    validation_prediction["predicted_revenue_eur"],
                )["rmse_eur"],
                "seasonal_naive_mae_eur": _error_metrics(
                    validation_actual,
                    baseline_prediction["seasonal_naive_revenue_eur"],
                )["mae_eur"],
                "seasonal_naive_rmse_eur": _error_metrics(
                    validation_actual,
                    baseline_prediction["seasonal_naive_revenue_eur"],
                )["rmse_eur"],
            }
        )

    summary = {
        metric: {
            "mean": mean(float(fold[metric]) for fold in fold_results),
            "std": stdev(float(fold[metric]) for fold in fold_results),
        }
        for metric in metric_names
    }
    return fold_results, summary


def evaluate_learning_curve(
    training: pd.DataFrame,
    train_sizes: tuple[int, ...] = LEARNING_CURVE_TRAIN_SIZES,
    n_estimators: int = 400,
) -> list[dict[str, float | int]]:
    """Measure fit/validation errors for increasing histories at one fixed origin."""
    ordered = training.sort_values("month").reset_index(drop=True)
    validation = ordered.iloc[-LEARNING_CURVE_VALIDATION_MONTHS:].copy().reset_index(drop=True)
    development_history = ordered.iloc[:-LEARNING_CURVE_VALIDATION_MONTHS].copy().reset_index(drop=True)
    results = []

    for training_size in train_sizes:
        if training_size > len(development_history):
            raise ValueError(f"Learning-curve training size {training_size} exceeds the available history.")
        prefix = development_history.iloc[-training_size:].copy().reset_index(drop=True)
        if prefix["month"].iloc[-1] + pd.offsets.MonthBegin(1) != validation["month"].iloc[0]:
            raise AssertionError("Every learning-curve prefix must end immediately before the fixed validation year.")
        model, features = _fit_fold_model(prefix, n_estimators)
        train_actual, train_prediction = _revenue_predictions_for_training(prefix, model, features)
        validation_prediction = forecast_recursively(model, prefix, validation["month"])
        baseline_prediction = seasonal_naive_forecast(prefix, validation["month"])
        validation_actual = validation["revenue_eur"].astype(float).reset_index(drop=True)
        train_metrics = _error_metrics(train_actual, train_prediction)
        validation_metrics = _error_metrics(validation_actual, validation_prediction["predicted_revenue_eur"])
        baseline_metrics = _error_metrics(validation_actual, baseline_prediction["seasonal_naive_revenue_eur"])
        results.append(
            {
                "training_months": training_size,
                "training_target_months": len(features),
                "training_mae_eur": train_metrics["mae_eur"],
                "training_rmse_eur": train_metrics["rmse_eur"],
                "validation_mae_eur": validation_metrics["mae_eur"],
                "validation_rmse_eur": validation_metrics["rmse_eur"],
                "seasonal_naive_mae_eur": baseline_metrics["mae_eur"],
                "seasonal_naive_rmse_eur": baseline_metrics["rmse_eur"],
            }
        )
    return results


def diagnose_fit(curve: list[dict[str, float | int]]) -> tuple[str, str, dict[str, float]]:
    """Classify fit from the largest-history gap and fixed-horizon baseline comparison."""
    first = curve[0]
    final = curve[-1]
    final_train_rmse = float(final["training_rmse_eur"])
    final_validation_rmse = float(final["validation_rmse_eur"])
    baseline_rmse = float(final["seasonal_naive_rmse_eur"])
    generalization_gap = (final_validation_rmse - final_train_rmse) / max(final_validation_rmse, 1.0)
    validation_improvement_pct = (
        (float(first["validation_rmse_eur"]) - final_validation_rmse)
        / max(float(first["validation_rmse_eur"]), 1.0)
        * 100
    )

    if generalization_gap >= 0.20:
        classification = "Overfitting"
        action = (
            "The largest-history validation RMSE remains at least 20% above training RMSE. "
            "First constrain tree complexity with a larger min_samples_leaf or max_depth, then compare the same folds."
        )
    elif final_validation_rmse >= baseline_rmse:
        classification = "Underfitting"
        action = (
            "Training and validation errors are relatively close, but validation RMSE does not beat seasonal-naive. "
            "Inspect the seasonal/growth feature representation and tune modestly within the same temporal folds."
        )
    else:
        classification = "Well fitted"
        action = (
            "The validation curve beats seasonal-naive without a large training/validation gap. "
            "Keep the current complexity and monitor later-period error rather than adding complexity."
        )

    values = {
        "final_generalization_gap_fraction": generalization_gap,
        "validation_rmse_improvement_from_smallest_to_largest_pct": validation_improvement_pct,
        "final_validation_rmse_eur": final_validation_rmse,
        "final_seasonal_naive_rmse_eur": baseline_rmse,
    }
    return classification, action, values


def save_learning_curve_plot(curve: list[dict[str, float | int]], path: Path) -> None:
    data = pd.DataFrame(curve)
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, metric, title in zip(
        axes,
        ("mae_eur", "rmse_eur"),
        ("MAE", "RMSE"),
        strict=True,
    ):
        axis.plot(data["training_months"], data[f"training_{metric}"], marker="o", label="Training")
        axis.plot(data["training_months"], data[f"validation_{metric}"], marker="o", label="Validation")
        axis.axhline(
            float(data[f"seasonal_naive_{metric}"].iloc[-1]),
            linestyle="--",
            color="#667085",
            label="Seasonal-naive validation",
        )
        axis.set(title=f"{title} by training history", xlabel="Training months", ylabel=f"{title} (EUR)")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("TrackFlow temporal learning curve (fixed 2023 validation year)")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _format_summary(summary: dict[str, dict[str, float]]) -> str:
    rows = []
    labels = {
        "training_mae_eur": "Training MAE",
        "validation_mae_eur": "Validation MAE",
        "training_rmse_eur": "Training RMSE",
        "validation_rmse_eur": "Validation RMSE",
        "seasonal_naive_mae_eur": "Seasonal-naive validation MAE",
        "seasonal_naive_rmse_eur": "Seasonal-naive validation RMSE",
    }
    for metric, label in labels.items():
        values = summary[metric]
        rows.append(f"| {label} | {values['mean']:,.2f} | {values['std']:,.2f} |")
    return "\n".join(rows)


def render_report(
    fold_results: list[dict[str, object]],
    summary: dict[str, dict[str, float]],
    curve: list[dict[str, float | int]],
    classification: str,
    action: str,
    diagnosis_values: dict[str, float],
) -> str:
    fold_rows = "\n".join(
        "| {fold} | {training_start}–{training_end} ({training_months}; {training_target_months} targets) "
        "| {validation_start}–{validation_end} ({validation_months}) | {training_mae_eur:,.2f} "
        "| {validation_mae_eur:,.2f} | {training_rmse_eur:,.2f} | {validation_rmse_eur:,.2f} |".format(**fold)
        for fold in fold_results
    )
    curve_rows = "\n".join(
        "| {training_months} | {training_target_months} | {training_mae_eur:,.2f} "
        "| {validation_mae_eur:,.2f} | {training_rmse_eur:,.2f} | {validation_rmse_eur:,.2f} | "
        "{seasonal_naive_rmse_eur:,.2f} |".format(**point)
        for point in curve
    )
    curve_validation = pd.date_range("2023-01-01", "2023-12-01", freq="MS")
    return f"""# TrackFlow Regression Model Evaluation

## Scope and method

- Model: existing fixed-seed Random Forest regressor (`random_state=42`); no hyperparameter search was performed.
- Evaluation data: only the 2016–2023 training period is used here. The 2024–2025 final test set is excluded from folds and the learning curve.
- Temporal cross-validation: expanding `TimeSeriesSplit`, {len(fold_results)} folds, {len(pd.date_range(fold_results[0]['validation_start'], fold_results[0]['validation_end'], freq='MS'))}-month validation windows. Each fold fits features on its training slice only and predicts its validation window recursively from that origin.
- Learning curve: one fixed validation horizon ({curve_validation[0]:%Y-%m}–{curve_validation[-1]:%Y-%m}), with trailing training histories of {', '.join(str(point['training_months']) for point in curve)} months, each ending in 2022-12. This isolates training-size changes from changes in validation dates.
- The 24-month lag/rolling warmup leaves fewer target rows than calendar months in each training window; the count is shown in both result tables.

## Cross-validation metrics

Fold metrics are calculated in EUR. Mean and sample standard deviation (`ddof=1`) across folds:

| Metric | Mean (EUR) | Std dev (EUR) |
| --- | ---: | ---: |
{_format_summary(summary)}

Per-fold results:

| Fold | Training period | Validation period | Train MAE | Validation MAE | Train RMSE | Validation RMSE |
| --- | --- | --- | ---: | ---: | ---: | ---: |
{fold_rows}

## Learning curve

See `data/eval/learning_curve.png`. The two panels show MAE and RMSE for the fixed 2023 horizon. The dashed line is a seasonal-naive baseline that repeats the final 12 training months; all its predictions are also fixed-origin.

| Training months | Usable training targets | Train MAE | Validation MAE | Train RMSE | Validation RMSE | Seasonal-naive RMSE |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{curve_rows}

## Diagnosis and corrective action

**Classification: {classification}.** At the largest training history, the validation RMSE is {diagnosis_values['final_validation_rmse_eur']:,.2f} EUR and the training/validation RMSE gap is {diagnosis_values['final_generalization_gap_fraction']:.1%}. Validation RMSE changes by {diagnosis_values['validation_rmse_improvement_from_smallest_to_largest_pct']:.1f}% between the smallest and largest histories. The same-horizon seasonal-naive RMSE is {diagnosis_values['final_seasonal_naive_rmse_eur']:,.2f} EUR.

**Action:** {action}

This diagnosis uses explicit heuristics: a gap of at least 20% indicates overfitting; otherwise, validation RMSE at or above the seasonal-naive RMSE indicates underfitting; a smaller gap with lower validation error than the baseline is classified as well fitted. Fold-to-fold standard deviations above describe temporal stability; they do not prove causal business costs.

## Metric choice and business-cost limitation

MAE is the primary stakeholder-facing measure because it is the average absolute euro error and is easy to interpret. RMSE is reported alongside it because squaring errors gives large misses more weight, which is relevant to seasonal peaks. The TrackFlow briefing does not specify whether over- or under-forecasting is more costly, so no asymmetric penalty or claim about the more expensive direction is made. The final holdout metrics remain in `reports/sales-forecasting/sales_forecast_metrics.json`; this evaluation does not change or tune against the final test period.
"""


def run_evaluation(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    n_estimators: int = 400,
) -> tuple[list[dict[str, object]], dict[str, dict[str, float]], list[dict[str, float | int]]]:
    data = load_sales_data(input_path)
    training, _final_test = split_sales_data(data)
    folds, summary = evaluate_temporal_cv(training, n_estimators=n_estimators)
    curve = evaluate_learning_curve(training, n_estimators=n_estimators)
    classification, action, diagnosis_values = diagnose_fit(curve)

    output_dir.mkdir(parents=True, exist_ok=True)
    save_learning_curve_plot(curve, output_dir / "learning_curve.png")
    report = render_report(folds, summary, curve, classification, action, diagnosis_values)
    (output_dir / "evaluation_report.md").write_text(report, encoding="utf-8")
    pd.DataFrame(folds).to_csv(output_dir / "temporal_cv_folds.csv", index=False)
    pd.DataFrame(curve).to_csv(output_dir / "learning_curve_metrics.csv", index=False)
    return folds, summary, curve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    run_evaluation(arguments.input, arguments.output_dir)
    print(f"Evaluation report: {arguments.output_dir / 'evaluation_report.md'}")
    print(f"Learning curve: {arguments.output_dir / 'learning_curve.png'}")


if __name__ == "__main__":
    main()
