"""Small, explainable chronological linear-trend forecasting baseline.

The functions accept only date/price observations. Production callers load these
from market_prices; they do not synthesize observations when history is absent.
"""

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Sequence


MIN_OBSERVATIONS = 60
MIN_SPAN_DAYS = 90


class InsufficientPriceHistory(ValueError):
    pass


@dataclass(frozen=True)
class ForecastResult:
    predicted_price: float
    mae: float
    mape_percent: float | None
    training_observations: int
    evaluation_observations: int
    as_of: date


def _fit_line(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        raise InsufficientPriceHistory("Historical dates do not span enough time.")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator
    return mean_y - slope * mean_x, slope


def forecast_modal_price(observations: Sequence[tuple[date, float]], horizon_days: int) -> ForecastResult:
    """Evaluate on the newest 20% chronologically, refit on all data, forecast."""
    if not 1 <= horizon_days <= 30:
        raise ValueError("horizon_days must be between 1 and 30.")
    ordered = sorted(observations, key=lambda item: item[0])
    if len(ordered) < MIN_OBSERVATIONS or (ordered[-1][0] - ordered[0][0]).days < MIN_SPAN_DAYS:
        raise InsufficientPriceHistory(
            f"At least {MIN_OBSERVATIONS} historical observations spanning {MIN_SPAN_DAYS} days are required."
        )
    if len({d for d, _ in ordered}) != len(ordered):
        raise ValueError("Historical series must contain at most one record per date.")
    prices = [float(value) for _, value in ordered]
    if any(not isfinite(value) or value < 0 for value in prices):
        raise ValueError("Historical modal prices must be finite and non-negative.")
    origin = ordered[0][0]
    xs = [(d - origin).days for d, _ in ordered]
    split = max(2, int(len(ordered) * 0.8))
    if split >= len(ordered):
        split = len(ordered) - 1
    intercept, slope = _fit_line(xs[:split], prices[:split])
    predictions = [max(0.0, intercept + slope * x) for x in xs[split:]]
    actuals = prices[split:]
    mae = sum(abs(a - p) for a, p in zip(actuals, predictions)) / len(actuals)
    nonzero = [(a, p) for a, p in zip(actuals, predictions) if a != 0]
    mape = (sum(abs(a - p) / abs(a) for a, p in nonzero) / len(nonzero) * 100) if nonzero else None

    intercept, slope = _fit_line(xs, prices)
    target_x = (ordered[-1][0] - origin).days + horizon_days
    predicted = max(0.0, intercept + slope * target_x)
    return ForecastResult(
        predicted_price=round(predicted, 2), mae=round(mae, 2),
        mape_percent=round(mape, 2) if mape is not None else None,
        training_observations=split, evaluation_observations=len(actuals), as_of=ordered[-1][0],
    )
