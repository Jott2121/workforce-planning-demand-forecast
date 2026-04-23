"""Tests for the demand forecast."""
from __future__ import annotations

import pandas as pd

from src.forecast import (
    SCENARIO_MULTIPLIERS,
    ForecastConfig,
    forecast_demand,
    roll_up_by_month,
)
from src.generate import ScenarioConfig, generate_all


def test_forecast_shape_and_columns():
    hist, pos, _ = generate_all(ScenarioConfig(seed=1))
    fc = forecast_demand(hist, pos, ForecastConfig(horizon_months=6))
    assert {"month", "business_unit", "skill_family", "forecast",
            "planned_hires", "forecast_lower", "forecast_upper", "scenario"}.issubset(fc.columns)
    assert fc["month"].nunique() == 6


def test_growth_scenario_larger_than_constrained():
    hist, pos, _ = generate_all(ScenarioConfig(seed=7))
    growth = forecast_demand(hist, pos, ForecastConfig(scenario="Growth")).forecast.sum()
    constrained = forecast_demand(
        hist, pos, ForecastConfig(scenario="Constrained")
    ).forecast.sum()
    assert growth > constrained, (
        "Growth scenario should produce more total demand than Constrained"
    )


def test_rollup_matches_total():
    hist, pos, _ = generate_all(ScenarioConfig(seed=3))
    fc = forecast_demand(hist, pos, ForecastConfig())
    rollup = roll_up_by_month(fc)
    assert abs(rollup["forecast"].sum() - fc["forecast"].sum()) < 1e-6


def test_scenario_multipliers_are_monotonic():
    assert (
        SCENARIO_MULTIPLIERS["Constrained"]
        < SCENARIO_MULTIPLIERS["Flat"]
        < SCENARIO_MULTIPLIERS["Base"]
        < SCENARIO_MULTIPLIERS["Growth"]
    )
