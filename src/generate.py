"""Realistic mock data generator for workforce planning and recruiter capacity.

Produces three related tables — `historical_fills`, `positions` (open and
planned requisitions), and `recruiters` — shaped like what a real deployment
would read from Workday, an ATS, and recruiter-operations reporting.

Calibrated against:
- Typical defense-industry hiring volumes (2-4% annual growth, 8-15% attrition)
- ClearanceJobs / SHRM time-to-fill benchmarks for cleared roles
- Published recruiter-throughput ranges (1.5-4 hires / recruiter / month)

All relationships are tunable via `ScenarioConfig` for stress-testing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.schema import (
    BUSINESS_UNITS,
    CLEARANCE_TTF_MULTIPLIER,
    CLEARANCE_TYPES,
    DEFAULT_RECRUITER_THROUGHPUT,
    LOCATIONS,
    SKILL_FAMILIES,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class ScenarioConfig:
    """Parameters for generating a workforce plan scenario.

    Defaults model a realistic mid-sized defense business unit: ~1,200 planned
    hires across a 12-month horizon, seasonal Q1/Q3 spikes, and a clearance
    mix tilted toward Secret (the most common level on defense programs).
    """

    seed: int = 42
    planning_horizon_months: int = 12
    annual_hiring_volume: int = 1200
    growth_rate: float = 0.05              # YoY hiring demand growth
    recruiters_per_bu: tuple[int, int] = (4, 12)  # uniform range
    clearance_mix: dict[str, float] = field(
        default_factory=lambda: {
            "None": 0.25,
            "Public Trust": 0.10,
            "Secret": 0.40,
            "Top Secret": 0.18,
            "TS/SCI": 0.07,
        }
    )
    skill_family_mix: dict[str, float] | None = None

    def __post_init__(self) -> None:
        # Default skill-family mix weighted toward engineering on the
        # assumption of a defense / aerospace enterprise.
        if self.skill_family_mix is None:
            self.skill_family_mix = {
                "Software Engineering": 0.18,
                "Systems Engineering": 0.16,
                "Cybersecurity": 0.08,
                "Data Science & Analytics": 0.05,
                "Mechanical Engineering": 0.12,
                "Electrical Engineering": 0.10,
                "Program / Project Management": 0.10,
                "Manufacturing Operations": 0.08,
                "Supply Chain": 0.05,
                "HR / People Analytics": 0.02,
                "Finance & Accounting": 0.04,
                "Business Development": 0.02,
            }


# -----------------------------------------------------------------------------
# Historical fills (lookback for baseline forecasting)
# -----------------------------------------------------------------------------


def _month_index(
    anchor: datetime, offset_months: int
) -> datetime:
    """Naive month arithmetic — good enough for monthly bucketing."""
    total = anchor.month - 1 + offset_months
    year = anchor.year + total // 12
    month = total % 12 + 1
    return datetime(year, month, 1)


def _seasonal_multiplier(month_num: int) -> float:
    """Seasonality pattern typical of enterprise hiring.

    Q1 pickup after headcount plan approval, Q2 slowdown, Q3 ramp ahead of
    fiscal-year end, Q4 dip around holidays. Amplitude of ±20 % around 1.0.
    """
    # Month 1..12 → phase 0..2π
    phase = 2 * np.pi * (month_num - 1) / 12
    # Two peaks at Feb-Mar and Aug-Sep
    return 1.0 + 0.15 * np.sin(phase - np.pi / 6) + 0.05 * np.sin(2 * phase)


def generate_historical_fills(
    config: ScenarioConfig,
    lookback_months: int = 24,
    anchor: datetime | None = None,
) -> pd.DataFrame:
    """Simulate the last N months of actual hires across the enterprise."""
    rng = np.random.default_rng(config.seed)
    anchor = anchor or datetime.today().replace(day=1)

    rows: list[dict] = []
    skill_families = list(config.skill_family_mix.keys())
    skill_weights = np.array(list(config.skill_family_mix.values()))
    skill_weights = skill_weights / skill_weights.sum()

    clearances = list(config.clearance_mix.keys())
    clearance_weights = np.array(list(config.clearance_mix.values()))
    clearance_weights = clearance_weights / clearance_weights.sum()

    for offset in range(-lookback_months, 0):
        month_start = _month_index(anchor, offset)
        seasonal = _seasonal_multiplier(month_start.month)
        # Pre-growth baseline -- older months hired slightly fewer people.
        trend = (1 + config.growth_rate) ** (offset / 12)
        base_hires = int(config.annual_hiring_volume / 12 * seasonal * trend)
        noise = rng.normal(1.0, 0.08)
        n_hires = max(0, int(base_hires * noise))

        families = rng.choice(skill_families, size=n_hires, p=skill_weights)
        bus = rng.choice(BUSINESS_UNITS, size=n_hires)
        locs = rng.choice(LOCATIONS, size=n_hires)
        clearances_sampled = rng.choice(
            clearances, size=n_hires, p=clearance_weights
        )
        for f, bu, loc, cl in zip(families, bus, locs, clearances_sampled):
            rows.append(
                {
                    "hire_month": month_start.strftime("%Y-%m"),
                    "business_unit": str(bu),
                    "location": str(loc),
                    "skill_family": str(f),
                    "clearance_type": str(cl),
                    "days_to_fill": int(
                        rng.normal(
                            60 * CLEARANCE_TTF_MULTIPLIER[cl],
                            14,
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Open and planned positions (the forward book)
# -----------------------------------------------------------------------------


def generate_positions(
    config: ScenarioConfig,
    anchor: datetime | None = None,
) -> pd.DataFrame:
    """Simulate open requisitions and planned positions for the forward horizon."""
    rng = np.random.default_rng(config.seed + 1)
    anchor = anchor or datetime.today().replace(day=1)

    skill_families = list(config.skill_family_mix.keys())
    skill_weights = np.array(list(config.skill_family_mix.values()))
    skill_weights = skill_weights / skill_weights.sum()

    clearances = list(config.clearance_mix.keys())
    clearance_weights = np.array(list(config.clearance_mix.values()))
    clearance_weights = clearance_weights / clearance_weights.sum()

    priorities = np.array(["Critical", "High", "Standard"])
    priority_weights = np.array([0.12, 0.38, 0.50])

    rows: list[dict] = []
    req_id = 100_000
    for offset in range(config.planning_horizon_months):
        month_start = _month_index(anchor, offset)
        seasonal = _seasonal_multiplier(month_start.month)
        trend = (1 + config.growth_rate) ** (offset / 12)
        n_positions = int(
            config.annual_hiring_volume / 12 * seasonal * trend
            * rng.normal(1.0, 0.06)
        )

        families = rng.choice(skill_families, size=n_positions, p=skill_weights)
        bus = rng.choice(BUSINESS_UNITS, size=n_positions)
        locs = rng.choice(LOCATIONS, size=n_positions)
        clearances_sampled = rng.choice(
            clearances, size=n_positions, p=clearance_weights
        )
        levels = rng.integers(1, 7, size=n_positions)
        prio = rng.choice(priorities, size=n_positions, p=priority_weights)

        for f, bu, loc, cl, lv, pr in zip(
            families, bus, locs, clearances_sampled, levels, prio
        ):
            req_id += 1
            rows.append(
                {
                    "requisition_id": f"REQ-{req_id}",
                    "business_unit": str(bu),
                    "location": str(loc),
                    "skill_family": str(f),
                    "job_level": int(lv),
                    "clearance_type": str(cl),
                    "planned_start_month": month_start.strftime("%Y-%m"),
                    "priority": str(pr),
                }
            )
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Recruiters
# -----------------------------------------------------------------------------

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Jamie", "Casey", "Riley",
    "Avery", "Quinn", "Sam", "Drew", "Cameron", "Blake", "Reese", "Skyler",
    "Hayden", "Peyton", "Rowan", "Sage", "Emerson",
]
_LAST_NAMES = [
    "Patel", "Nguyen", "Khan", "Garcia", "Chen", "Kim", "Martinez",
    "Rodriguez", "Lopez", "Singh", "Cohen", "Brown", "Johnson", "Hill",
    "Murphy", "Okafor", "Yamamoto", "Andersen", "Dubois", "Reyes",
]


def generate_recruiters(config: ScenarioConfig) -> pd.DataFrame:
    """Simulate the recruiter roster with realistic throughput and coverage."""
    rng = np.random.default_rng(config.seed + 2)
    rows: list[dict] = []
    recruiter_id = 50_000

    for bu in BUSINESS_UNITS:
        n_recruiters = int(rng.integers(*config.recruiters_per_bu))
        for _ in range(n_recruiters):
            recruiter_id += 1
            primary = str(rng.choice(SKILL_FAMILIES))
            # Secondary coverage: 0-2 additional skill families.
            n_secondary = int(rng.integers(0, 3))
            secondaries = rng.choice(
                [s for s in SKILL_FAMILIES if s != primary],
                size=n_secondary,
                replace=False,
            )
            base_tp = DEFAULT_RECRUITER_THROUGHPUT.get(primary, 2.5)
            throughput = float(np.clip(rng.normal(base_tp, 0.5), 0.5, 6.0))
            # Most recruiters are fully dedicated; some are 50-75% allocated.
            alloc = float(rng.choice([1.0, 1.0, 1.0, 0.75, 0.5], p=[0.6, 0.15, 0.1, 0.1, 0.05]))
            rows.append(
                {
                    "recruiter_id": f"RCR-{recruiter_id}",
                    "name": f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
                    "business_unit": bu,
                    "primary_skill_family": primary,
                    "secondary_skill_families": ", ".join(sorted(secondaries)),
                    "throughput_hires_per_month": round(throughput, 2),
                    "allocation_pct": alloc,
                }
            )
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Public entry points
# -----------------------------------------------------------------------------


def generate_all(
    config: ScenarioConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Produce all three core tables from a single config."""
    config = config or ScenarioConfig()
    return (
        generate_historical_fills(config),
        generate_positions(config),
        generate_recruiters(config),
    )


def write_csvs(out_dir: Path = DATA_DIR) -> None:
    """Write all three tables to `data/` so downstream consumers have a fixture."""
    config = ScenarioConfig()
    hist, positions, recruiters = generate_all(config)
    hist.to_csv(out_dir / "historical_fills.csv", index=False)
    positions.to_csv(out_dir / "positions.csv", index=False)
    recruiters.to_csv(out_dir / "recruiters.csv", index=False)
    print(f"Wrote {len(hist):,} historical fills to {out_dir}/historical_fills.csv")
    print(f"Wrote {len(positions):,} positions to {out_dir}/positions.csv")
    print(f"Wrote {len(recruiters)} recruiters to {out_dir}/recruiters.csv")


if __name__ == "__main__":
    write_csvs()
