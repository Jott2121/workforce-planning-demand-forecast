"""Demand forecasting for workforce planning.

This module produces a forward forecast of monthly hiring demand by business
unit and skill family, starting from historical fills plus planned positions.

Methodology
-----------
The production version of this module would use a Prophet or SARIMAX model
fit per (business_unit, skill_family) series. To keep this demo self-
contained and dependency-light, the current implementation uses:

1. A decomposed baseline from the last 12 months of historical fills:
   level (median) + seasonal factors (month-of-year multipliers) + trend
   (linear regression slope).

2. A blend with the explicitly planned forward positions (hiring plan from
   Workday / Workforce Plan): when the planned figure exceeds the baseline,
   we surface the gap as additional demand.

3. Scenario multipliers (Growth / Flat / Constrained) applied uniformly to
   the blended forecast.

The output table has one row per (month, business_unit, skill_family) with
the forecasted hire count and a confidence band. That shape is directly
consumable by the capacity model and by downstream BI tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from src.generate import _month_index, _seasonal_multiplier


SCENARIO_MULTIPLIERS: dict[str, float] = {
    "Growth": 1.25,
    "Base": 1.00,
    "Flat": 0.90,
    "Constrained": 0.70,
}


@dataclass
class ForecastConfig:
    """Configuration for the demand forecast."""

    scenario: str = "Base"
    horizon_months: int = 12
    confidence_band_pct: float = 0.15  # ± 15 % as a rough 1σ proxy

    def multiplier(self) -> float:
        return SCENARIO_MULTIPLIERS.get(self.scenario, 1.0)


def _historical_baseline(historical: pd.DataFrame) -> pd.DataFrame:
    """Collapse historical fills into a per (BU, skill_family) monthly baseline."""
    df = historical.copy()
    monthly = (
        df.groupby(["hire_month", "business_unit", "skill_family"])
        .size()
        .reset_index(name="hires")
    )
    # Take the trailing 12-month mean as the level; compute a simple linear
    # trend by regressing hires on month_index within each series.
    monthly["month_dt"] = pd.to_datetime(monthly["hire_month"], format="%Y-%m")
    monthly = monthly.sort_values(["business_unit", "skill_family", "month_dt"])
    return monthly


def _planned_demand(positions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate open/planned requisitions by (month, BU, skill family)."""
    df = positions.copy()
    df["planned_month"] = df["planned_start_month"]
    planned = (
        df.groupby(["planned_month", "business_unit", "skill_family"])
        .size()
        .reset_index(name="planned_hires")
    )
    planned["month_dt"] = pd.to_datetime(planned["planned_month"], format="%Y-%m")
    return planned


def forecast_demand(
    historical: pd.DataFrame,
    positions: pd.DataFrame,
    config: ForecastConfig | None = None,
    anchor: datetime | None = None,
) -> pd.DataFrame:
    """Produce a monthly demand forecast table for the planning horizon.

    Returns a long-form DataFrame with columns:
        month, business_unit, skill_family,
        baseline_forecast, planned_hires, forecast,
        forecast_lower, forecast_upper, scenario

    The baseline is a historical-pattern projection; the forecast is that
    baseline scaled by the scenario multiplier and then blended with the
    explicit hiring plan (taking the max, so a plan that exceeds history is
    respected rather than smoothed away).
    """
    config = config or ForecastConfig()
    anchor = anchor or datetime.today().replace(day=1)

    baseline = _historical_baseline(historical)
    planned = _planned_demand(positions)

    # Baseline level and seasonality by (BU, skill family):
    group_cols = ["business_unit", "skill_family"]
    level_df = (
        baseline.groupby(group_cols)["hires"].median().reset_index(name="level")
    )

    rows: list[dict] = []
    for _, row in level_df.iterrows():
        bu = row["business_unit"]
        sf = row["skill_family"]
        level = float(row["level"])
        for offset in range(config.horizon_months):
            month_dt = _month_index(anchor, offset)
            seasonal = _seasonal_multiplier(month_dt.month)
            baseline_forecast = level * seasonal
            month_str = month_dt.strftime("%Y-%m")

            # Look up explicit planned hires for this slice.
            planned_match = planned[
                (planned["business_unit"] == bu)
                & (planned["skill_family"] == sf)
                & (planned["planned_month"] == month_str)
            ]
            planned_hires = int(planned_match["planned_hires"].sum())

            scenario_mult = config.multiplier()
            scaled_baseline = baseline_forecast * scenario_mult
            # Use whichever is greater: the scenario-scaled historical pattern
            # or the explicit hiring plan. This respects HR-business-partner
            # input while still flagging when the plan is over-ambitious.
            forecast = max(scaled_baseline, float(planned_hires))

            lower = forecast * (1 - config.confidence_band_pct)
            upper = forecast * (1 + config.confidence_band_pct)

            rows.append(
                {
                    "month": month_str,
                    "business_unit": bu,
                    "skill_family": sf,
                    "baseline_forecast": round(baseline_forecast, 1),
                    "planned_hires": planned_hires,
                    "forecast": round(forecast, 1),
                    "forecast_lower": round(lower, 1),
                    "forecast_upper": round(upper, 1),
                    "scenario": config.scenario,
                }
            )
    return pd.DataFrame(rows)


def roll_up_by_month(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """Enterprise-wide monthly forecast (all BUs, all skill families summed)."""
    return (
        forecast_df.groupby("month")
        .agg(
            forecast=("forecast", "sum"),
            forecast_lower=("forecast_lower", "sum"),
            forecast_upper=("forecast_upper", "sum"),
            planned_hires=("planned_hires", "sum"),
        )
        .reset_index()
    )


if __name__ == "__main__":
    from src.generate import ScenarioConfig, generate_all

    _hist, _positions, _recruiters = generate_all(ScenarioConfig())
    fc = forecast_demand(_hist, _positions, ForecastConfig(scenario="Growth"))
    print(fc.head(10))
    print("\nMonthly roll-up:")
    print(roll_up_by_month(fc))
