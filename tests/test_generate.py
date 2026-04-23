"""Tests for the mock data generator."""
from __future__ import annotations

import pandas as pd

from src.generate import ScenarioConfig, generate_all
from src.schema import BUSINESS_UNITS, CLEARANCE_TYPES, SKILL_FAMILIES


def test_all_three_tables_produced():
    hist, pos, rec = generate_all(ScenarioConfig(seed=123))
    assert len(hist) > 0, "historical fills should not be empty"
    assert len(pos) > 0, "positions should not be empty"
    assert len(rec) > 0, "recruiters should not be empty"


def test_schema_enforced():
    hist, pos, rec = generate_all(ScenarioConfig(seed=1))
    assert set(hist["business_unit"]).issubset(set(BUSINESS_UNITS))
    assert set(pos["business_unit"]).issubset(set(BUSINESS_UNITS))
    assert set(rec["business_unit"]).issubset(set(BUSINESS_UNITS))
    assert set(pos["clearance_type"]).issubset(set(CLEARANCE_TYPES))
    assert set(pos["skill_family"]).issubset(set(SKILL_FAMILIES))


def test_deterministic_with_seed():
    h1, p1, r1 = generate_all(ScenarioConfig(seed=7))
    h2, p2, r2 = generate_all(ScenarioConfig(seed=7))
    pd.testing.assert_frame_equal(h1, h2)
    pd.testing.assert_frame_equal(p1, p2)
    pd.testing.assert_frame_equal(r1, r2)


def test_growth_rate_increases_later_periods():
    config = ScenarioConfig(seed=42, growth_rate=0.20, annual_hiring_volume=1200)
    hist, pos, _ = generate_all(config)
    # Forward positions should on average exceed historical fills under
    # positive growth.
    monthly_hist = hist.groupby("hire_month").size().mean()
    monthly_pos = pos.groupby("planned_start_month").size().mean()
    assert monthly_pos > monthly_hist, (
        "Expected forward positions to exceed historical pace under positive growth"
    )


def test_clearance_mix_respects_weights():
    config = ScenarioConfig(
        seed=42,
        clearance_mix={
            "None": 0.50,
            "Public Trust": 0.20,
            "Secret": 0.20,
            "Top Secret": 0.08,
            "TS/SCI": 0.02,
        },
    )
    _, pos, _ = generate_all(config)
    shares = pos["clearance_type"].value_counts(normalize=True)
    # Each empirical share should be within ±5 pp of target (with the sample
    # sizes here this is a loose but safe tolerance).
    for label, target in config.clearance_mix.items():
        assert abs(shares.get(label, 0) - target) < 0.05
