"""Tests for the recruiter capacity model."""
from __future__ import annotations

import pandas as pd

from src.capacity import (
    SECONDARY_COVERAGE_FACTOR,
    aggregate_capacity,
    compute_coverage,
    compute_recruiter_capacity,
    rollup_bottlenecks,
)
from src.forecast import ForecastConfig, forecast_demand
from src.generate import ScenarioConfig, generate_all


def test_primary_capacity_full():
    rec = pd.DataFrame(
        [{
            "recruiter_id": "RCR-1",
            "name": "Test",
            "business_unit": "Aeronautics",
            "primary_skill_family": "Software Engineering",
            "secondary_skill_families": "",
            "throughput_hires_per_month": 3.0,
            "allocation_pct": 1.0,
        }]
    )
    cap = compute_recruiter_capacity(rec)
    assert len(cap) == 1
    assert cap["monthly_capacity"].iloc[0] == 3.0


def test_secondary_capacity_haircut():
    rec = pd.DataFrame(
        [{
            "recruiter_id": "RCR-1",
            "name": "Test",
            "business_unit": "Aeronautics",
            "primary_skill_family": "Software Engineering",
            "secondary_skill_families": "Cybersecurity",
            "throughput_hires_per_month": 3.0,
            "allocation_pct": 1.0,
        }]
    )
    cap = compute_recruiter_capacity(rec)
    secondary_row = cap[cap["coverage_type"] == "secondary"].iloc[0]
    assert abs(secondary_row["monthly_capacity"] - 3.0 * SECONDARY_COVERAGE_FACTOR) < 1e-9


def test_coverage_columns():
    hist, pos, rec = generate_all(ScenarioConfig(seed=1))
    fc = forecast_demand(hist, pos, ForecastConfig())
    cov = compute_coverage(fc, rec, pos)
    for col in ["effective_capacity", "coverage_ratio", "gap", "bottleneck_flag"]:
        assert col in cov.columns


def test_bottleneck_flagging():
    hist, pos, rec = generate_all(ScenarioConfig(seed=1))
    # Force a strong growth scenario so bottlenecks should exist.
    fc = forecast_demand(hist, pos, ForecastConfig(scenario="Growth"))
    cov = compute_coverage(fc, rec, pos)
    assert set(cov["bottleneck_flag"]).issubset({"Bottleneck", "Tight", "Covered"})


def test_rollup_bottlenecks_nonnegative_gap():
    hist, pos, rec = generate_all(ScenarioConfig(seed=1))
    fc = forecast_demand(hist, pos, ForecastConfig(scenario="Growth"))
    cov = compute_coverage(fc, rec, pos)
    rollup = rollup_bottlenecks(cov)
    assert (rollup["total_gap_hires"] >= 0).all()
