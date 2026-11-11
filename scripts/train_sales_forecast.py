#!/usr/bin/env python3
"""Train and evaluate a TrackFlow monthly revenue forecast.

Run from the repository root with:
    python scripts/train_sales_forecast.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPOSITORY_ROOT / "data" / "raw" / "trackflow_sales.csv"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "reports" / "sales-forecasting"
EXPECTED_MONTHS = pd.date_range("2016-01-01", "2025-12-01", freq="MS")
EXPECTED_COLUMNS = (
    "month",
    "revenue_eur",
    "shipments_processed",
    "avg_revenue_per_shipment_eur",
    "market",
)
FEATURE_COLUMNS = [
    "month_sin",
    "month_cos",
    "year_parity",
    "growth_lag_1",
    "growth_rolling_mean_3",
    "growth_rolling_mean_12",
    "growth_rolling_std_12",
]


def validate_sales_data(data: pd.DataFrame) -> pd.DataFrame:
    """Return sorted consolidated rows after validating the context contract."""
    if tuple(data.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Sales CSV columns must exactly match, in order: "
            f"{list(EXPECTED_COLUMNS)}; received {list(data.columns)}."
        )

    cleaned = data.copy()
    cleaned["market"] = cleaned["market"].astype("string").str.strip().str.lower()
    if cleaned["market"].isna().any() or set(cleaned["market"].unique()) != {"consolidated"}:
        raise ValueError("The upstream TrackFlow sales file must contain only consolidated rows.")

    cleaned["month"] = pd.to_datetime(cleaned["month"], errors="coerce")
    if cleaned["month"].isna().any():
        raise ValueError("The month column contains invalid dates.")
    if not cleaned["month"].dt.is_month_start.all():
        raise ValueError("Every month value must be the first day of its month.")

    for column in ("revenue_eur", "shipments_processed", "avg_revenue_per_shipment_eur"):
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        if cleaned[column].isna().any() or not np.isfinite(cleaned[column]).all():
            raise ValueError(f"The {column} column must contain finite numeric values.")
    if (cleaned["shipments_processed"] % 1 != 0).any():
        raise ValueError("shipments_processed must contain whole-number shipment counts.")

    consolidated = cleaned.copy()
    if (consolidated["revenue_eur"] <= 0).any():
        raise ValueError("All consolidated revenue_eur values must be positive.")
    if (consolidated["shipments_processed"] < 0).any():
        raise ValueError("shipments_processed cannot be negative.")
    if consolidated["month"].duplicated().any():
        raise ValueError("The consolidated data contains duplicate months.")

    consolidated = consolidated.sort_values("month").reset_index(drop=True)
    actual_months = pd.DatetimeIndex(consolidated["month"])
    if not actual_months.equals(EXPECTED_MONTHS):
        missing_months = EXPECTED_MONTHS.difference(actual_months)
        extra_months = actual_months.difference(EXPECTED_MONTHS)
        raise ValueError(
            "Expected exactly one consolidated row per month from 2016-01 to 2025-12; "
            f"missing={missing_months.strftime('%Y-%m').tolist()}, "
            f"unexpected={extra_months.strftime('%Y-%m').tolist()}."
        )
    return consolidated


def load_sales_data(path: Path = DEFAULT_INPUT) -> pd.DataFrame:
    """Load and validate the TrackFlow sales CSV."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Sales CSV not found: {path}. Add the provided TrackFlow dataset; "
            "the training script does not generate or replace historical sales."
        )
    return validate_sales_data(pd.read_csv(path))


def split_sales_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split chronologically into the first 8 years (96 months) and last 2 (24)."""
    ordered = data.sort_values("month").reset_index(drop=True)
    if len(ordered) != 120 or ordered["month"].nunique() != 120:
        raise ValueError("The 8/2-year split requires 120 unique monthly observations.")
    if not pd.DatetimeIndex(ordered["month"]).equals(EXPECTED_MONTHS):
        raise ValueError("The split requires complete monthly data from 2016-01 to 2025-12.")

    train = ordered.iloc[:96].copy().reset_index(drop=True)
    test = ordered.iloc[96:].copy().reset_index(drop=True)
    if len(train) != 96 or len(test) != 24:
        raise AssertionError("Unexpected chronological split sizes.")
    return train, test


def context_pattern_diagnostics(data: pd.DataFrame) -> dict[str, object]:
    """Summarize observed annual growth and within-year seasonality without altering data."""
    diagnostics = data.assign(year=data["month"].dt.year, month_number=data["month"].dt.month)
    annual_revenue = diagnostics.groupby("year")["revenue_eur"].sum()
    annual_growth = annual_revenue.pct_change().dropna() * 100
    expected_growth = np.asarray([9.0 if index % 2 == 0 else 3.0 for index in range(len(annual_growth))])
    growth_deviations = np.abs(annual_growth.to_numpy() - expected_growth)

    diagnostics["year_mean_revenue"] = diagnostics.groupby("year")["revenue_eur"].transform("mean")
    diagnostics["within_year_index"] = diagnostics["revenue_eur"] / diagnostics["year_mean_revenue"] - 1
    seasonal_index = diagnostics.groupby("month_number")["within_year_index"].mean() * 100
    return {
        "annual_total_growth_pct_by_year": {
            str(int(year)): round(float(value), 2) for year, value in annual_growth.items()
        },
        "max_deviation_from_alternating_9_3_pct_points": round(float(growth_deviations.max()), 2),
        "within_year_seasonality_pct_by_month": {
            str(int(month)): round(float(value), 2) for month, value in seasonal_index.items()
        },
    }


def _calendar_features(months: pd.Series | pd.DatetimeIndex, origin_year: int) -> pd.DataFrame:
    dates = pd.DatetimeIndex(months)
    angle = 2 * np.pi * (dates.month.to_numpy() - 1) / 12
    features = pd.DataFrame(
        {
            "month_sin": np.sin(angle),
            "month_cos": np.cos(angle),
            "year_parity": (dates.year.to_numpy() - origin_year) % 2,
        },
        index=dates,
    )
    return features


def build_training_matrix(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build causal features for predicting year-over-year monthly growth."""
    revenue = train["revenue_eur"].astype(float).reset_index(drop=True)
    growth_ratio = revenue / revenue.shift(12)
    origin_year = int(pd.DatetimeIndex(train["month"]).year.min())
    features = _calendar_features(train["month"], origin_year)
    prior_growth = growth_ratio.shift(1)
    features["growth_lag_1"] = prior_growth.to_numpy()
    features["growth_rolling_mean_3"] = prior_growth.rolling(3, min_periods=3).mean().to_numpy()
    features["growth_rolling_mean_12"] = prior_growth.rolling(12, min_periods=12).mean().to_numpy()
    features["growth_rolling_std_12"] = prior_growth.rolling(12, min_periods=12).std(ddof=0).to_numpy()

    targets = pd.Series(growth_ratio.to_numpy(), index=features.index, name="growth_ratio")
    valid_rows = features[FEATURE_COLUMNS].notna().all(axis=1) & targets.notna()
    return features.loc[valid_rows, FEATURE_COLUMNS], targets.loc[valid_rows]


def _forecast_features(history: list[float], month: pd.Timestamp, origin_year: int) -> pd.DataFrame:
    growth_history = np.asarray(
        [history[index] / history[index - 12] for index in range(12, len(history))],
        dtype=float,
    )
    if len(growth_history) < 12:
        raise ValueError("At least 24 months of history are required for forecasting.")

    row = _calendar_features(pd.DatetimeIndex([month]), origin_year).iloc[0].to_dict()
    prior_growth = growth_history[-12:]
    row.update(
        {
            "growth_lag_1": float(prior_growth[-1]),
            "growth_rolling_mean_3": float(prior_growth[-3:].mean()),
            "growth_rolling_mean_12": float(prior_growth.mean()),
            "growth_rolling_std_12": float(prior_growth.std(ddof=0)),
        }
    )
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def forecast_recursively(
    model: RandomForestRegressor,
    train: pd.DataFrame,
    future_months: pd.Series | pd.DatetimeIndex,
) -> pd.DataFrame:
    """Forecast months using only training history and earlier predictions."""
    history = train["revenue_eur"].astype(float).tolist()
    train_months = pd.DatetimeIndex(train["month"])
    months = pd.DatetimeIndex(future_months)
    expected_future = pd.date_range(train_months[-1] + pd.offsets.MonthBegin(1), periods=len(months), freq="MS")
    if not months.equals(expected_future):
        raise ValueError("Forecast months must be consecutive and start after the training period.")

    origin_year = int(train_months.year.min())
    forecast_rows: list[dict[str, float | pd.Timestamp]] = []
    for month in months:
        features = _forecast_features(history, month, origin_year)
        feature_values = features.to_numpy(dtype=float)
        tree_growth = np.asarray(
            [estimator.predict(feature_values)[0] for estimator in model.estimators_],
            dtype=float,
        )
        prior_year_revenue = history[-12]
        predicted_growth = max(float(tree_growth.mean()), 0.01)
        lower_growth = max(float(np.quantile(tree_growth, 0.10)), 0.01)
        upper_growth = max(float(np.quantile(tree_growth, 0.90)), lower_growth)
        prediction = prior_year_revenue * predicted_growth
        lower = prior_year_revenue * lower_growth
        upper = prior_year_revenue * upper_growth
        history.append(prediction)
        forecast_rows.append(
            {
                "month": month,
                "predicted_revenue_eur": prediction,
                "tree_p10_revenue_eur": lower,
                "tree_p90_revenue_eur": upper,
            }
        )
    return pd.DataFrame(forecast_rows)


def seasonal_naive_forecast(
    train: pd.DataFrame,
    future_months: pd.Series | pd.DatetimeIndex,
) -> pd.DataFrame:
    """Fixed-origin seasonal-naive forecast, recursively repeating the last 12 months."""
    history = train["revenue_eur"].astype(float).tolist()
    train_months = pd.DatetimeIndex(train["month"])
    months = pd.DatetimeIndex(future_months)
    expected_future = pd.date_range(train_months[-1] + pd.offsets.MonthBegin(1), periods=len(months), freq="MS")
    if not months.equals(expected_future):
        raise ValueError("Forecast months must be consecutive and start after the training period.")

    rows = []
    for month in months:
        prediction = history[-12]
        rows.append({"month": month, "seasonal_naive_revenue_eur": prediction})
        history.append(prediction)
    return pd.DataFrame(rows)


def population_stability_index(reference: pd.Series, comparison: pd.Series, bins: int = 10) -> float:
    """Calculate PSI using reference quantile bins and a small proportion floor."""
    reference_values = np.asarray(reference, dtype=float)
    comparison_values = np.asarray(comparison, dtype=float)
    edges = np.unique(np.quantile(reference_values, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        low = float(reference_values.min())
        high = float(reference_values.max())
        if low == high:
            width = max(abs(low) * 0.01, 1.0)
            low -= width
            high += width
        edges = np.linspace(low, high, bins + 1)
    edges[0] = -np.inf
    edges[-1] = np.inf

    reference_counts = np.histogram(reference_values, bins=edges)[0].astype(float)
    comparison_counts = np.histogram(comparison_values, bins=edges)[0].astype(float)
    reference_share = reference_counts / reference_counts.sum()
    comparison_share = comparison_counts / comparison_counts.sum()
    floor = 1e-6
    reference_share = np.clip(reference_share, floor, None)
    comparison_share = np.clip(comparison_share, floor, None)
    reference_share /= reference_share.sum()
    comparison_share /= comparison_share.sum()
    return float(np.sum((comparison_share - reference_share) * np.log(comparison_share / reference_share)))


def _gini(actual: np.ndarray, predicted: np.ndarray) -> float:
    order = np.argsort(predicted, kind="mergesort")
    ordered_actual = actual[order]
    ranks = np.arange(1, len(actual) + 1)
    return float(np.sum((2 * ranks - len(actual) - 1) * ordered_actual) / (len(actual) * actual.sum()))


def normalized_gini(actual: pd.Series, predicted: pd.Series) -> float | None:
    """Return normalized regression Gini; 1 is perfect ranking, 0 is no lift."""
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    ideal_gini = _gini(actual_values, actual_values)
    if np.isclose(ideal_gini, 0):
        return None
    return _gini(actual_values, predicted_values) / ideal_gini


def evaluate_forecast(
    train: pd.DataFrame,
    test: pd.DataFrame,
    forecast: pd.DataFrame,
    baseline: pd.DataFrame,
) -> dict[str, object]:
    actual = test["revenue_eur"].astype(float)
    predicted = forecast["predicted_revenue_eur"].astype(float)
    baseline_predicted = baseline["seasonal_naive_revenue_eur"].astype(float)
    mean_revenue = float(actual.mean())

    def regression_metrics(values: pd.Series) -> dict[str, float | None]:
        mse = float(mean_squared_error(actual, values))
        return {
            "mse_eur_squared": mse,
            "rmse_eur": float(np.sqrt(mse)),
            "rmse_pct_of_test_mean_revenue": float(np.sqrt(mse) / mean_revenue * 100),
            "normalized_gini": normalized_gini(actual, values),
            "r2_score": float(r2_score(actual, values)),
        }

    return {
        "evaluation_protocol": (
            "Fixed-origin recursive 24-month forecast; holdout actuals are never fed into later horizons. "
            "No rolling one-step evaluation is reported."
        ),
        "random_forest": regression_metrics(predicted),
        "seasonal_naive_baseline": regression_metrics(baseline_predicted),
        "psi_revenue_distribution_train_vs_test": population_stability_index(train["revenue_eur"], actual),
        "psi_market_mix": None,
        "psi_market_mix_note": (
            "Unavailable: the source contains consolidated rows only; no US/Spain mix is inferred or fabricated."
        ),
        "k2_score": None,
        "k2_score_note": (
            "Neither supplied context defines K2 Score. R2 is reported separately; treating K2 as R2 is unconfirmed."
        ),
        "r2_score": float(r2_score(actual, predicted)),
    }


def save_forecast_plot(
    train: pd.DataFrame,
    predictions: pd.DataFrame,
    output_path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(train["month"], train["revenue_eur"], label="Training revenue", color="#4c6475")
    axis.plot(
        predictions["month"],
        predictions["actual_revenue_eur"],
        label="Actual test revenue",
        color="#1b7a59",
    )
    axis.plot(
        predictions["month"],
        predictions["predicted_revenue_eur"],
        label="Random Forest fixed-origin forecast",
        color="#c24d35",
    )
    axis.plot(
        predictions["month"],
        predictions["seasonal_naive_revenue_eur"],
        label="Seasonal-naive baseline",
        color="#4778a8",
        linestyle="--",
    )
    axis.fill_between(
        predictions["month"],
        predictions["tree_p10_revenue_eur"],
        predictions["tree_p90_revenue_eur"],
        color="#c24d35",
        alpha=0.18,
        label="Tree prediction spread (10th-90th percentile; not calibrated)",
    )
    axis.set(title="TrackFlow monthly revenue forecast", xlabel="Month", ylabel="Revenue (EUR)")
    axis.grid(alpha=0.2)
    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def run_forecast(input_path: Path, output_dir: Path) -> dict[str, object]:
    data = load_sales_data(input_path)
    train, test = split_sales_data(data)
    features, targets = build_training_matrix(train)
    model = RandomForestRegressor(
        n_estimators=400,
        min_samples_leaf=2,
        max_features=1.0,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features, targets)
    forecast = forecast_recursively(model, train, test["month"])
    baseline = seasonal_naive_forecast(train, test["month"])
    metrics = evaluate_forecast(train, test, forecast, baseline)
    metrics["train_period"] = [train["month"].min().strftime("%Y-%m"), train["month"].max().strftime("%Y-%m")]
    metrics["test_period"] = [test["month"].min().strftime("%Y-%m"), test["month"].max().strftime("%Y-%m")]
    metrics["train_months"] = len(train)
    metrics["test_months"] = len(test)
    metrics["model_selection"] = (
        "Random Forest was selected for the 96-month training set because bagged trees are explainable and need "
        "little tuning. It predicts year-over-year growth ratios, which avoids relying on tree extrapolation of "
        "raw revenue; a seasonal-naive baseline is included for comparison."
    )
    metrics["random_state"] = 42
    metrics["data_pattern_diagnostics"] = context_pattern_diagnostics(data)

    predictions = test[["month", "revenue_eur"]].rename(columns={"revenue_eur": "actual_revenue_eur"})
    predictions = predictions.merge(forecast, on="month", validate="one_to_one")
    predictions = predictions.merge(baseline, on="month", validate="one_to_one")

    output_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_dir / "sales_forecast_test.csv", index=False)
    with (output_dir / "sales_forecast_metrics.json").open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=2, allow_nan=False)
    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "target": "year_over_year_revenue_ratio",
            "random_state": 42,
        },
        output_dir / "sales_forecast_model.joblib",
    )
    save_forecast_plot(train, predictions, output_dir / "sales_forecast.png")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the TrackFlow sales CSV.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for model and reports.")
    arguments = parser.parse_args()
    try:
        metrics = run_forecast(arguments.input, arguments.output_dir)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(metrics, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
