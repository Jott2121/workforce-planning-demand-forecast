"""Recruiter capacity model and bottleneck detection.

Given a demand forecast and a recruiter roster, compute monthly recruiter
capacity by (business_unit, skill_family) and flag segments where demand
exceeds capacity.

Capacity model
--------------
For each recruiter r:
    monthly_capacity_r = r.throughput_hires_per_month * r.allocation_pct

Recruiter coverage of a skill family:
- Primary skill family: 100% of capacity attributed
- Each secondary skill family: 35% of capacity (representing partial focus
  and context-switch overhead)

In aggregate, total (business_unit, skill_family) capacity per month:
    capacity = Σ over recruiters in that BU:
        (1 if primary else 0.35) * monthly_capacity_r

Cleared-role haircut
--------------------
Cleared requisitions (Secret / TS / TS/SCI) take meaningfully longer to fill
than unclassified roles. Since the forecast is denominated in *hires*, not
*reqs*, we apply a proportional capacity haircut based on the clearance mix
of the forecast slice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.schema import CLEARANCE_TTF_MULTIPLIER

SECONDARY_COVERAGE_FACTOR: float = 0.35


def compute_recruiter_capacity(recruiters: pd.DataFrame) -> pd.DataFrame:
    """Expand the recruiter roster into one row per (recruiter, skill_family).

    Returns a long-form table with monthly capacity attributed to each
    covered skill family.
    """
    rows: list[dict] = []
    for _, r in recruiters.iterrows():
        monthly_cap = r["throughput_hires_per_month"] * r["allocation_pct"]
        # Primary
        rows.append(
            {
                "recruiter_id": r["recruiter_id"],
                "name": r["name"],
                "business_unit": r["business_unit"],
                "skill_family": r["primary_skill_family"],
                "coverage_type": "primary",
                "monthly_capacity": monthly_cap,
            }
        )
        # Secondary
        secondaries = [s.strip() for s in str(r["secondary_skill_families"]).split(",") if s.strip()]
        for sf in secondaries:
            rows.append(
                {
                    "recruiter_id": r["recruiter_id"],
                    "name": r["name"],
                    "business_unit": r["business_unit"],
                    "skill_family": sf,
                    "coverage_type": "secondary",
                    "monthly_capacity": monthly_cap * SECONDARY_COVERAGE_FACTOR,
                }
            )
    return pd.DataFrame(rows)


def aggregate_capacity(capacity_long: pd.DataFrame) -> pd.DataFrame:
    """Aggregate recruiter capacity to (BU, skill_family)."""
    return (
        capacity_long.groupby(["business_unit", "skill_family"])
        .agg(
            monthly_capacity=("monthly_capacity", "sum"),
            recruiter_count=("recruiter_id", "nunique"),
        )
        .reset_index()
    )


def compute_coverage(
    forecast_df: pd.DataFrame,
    recruiters: pd.DataFrame,
    positions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """For each (month, BU, skill_family), compute demand vs capacity.

    If `positions` is supplied, applies a clearance-weighted haircut based on
    the clearance mix of the planned requisitions for that slice.

    Returns columns: month, business_unit, skill_family, forecast, capacity,
    effective_capacity, coverage_ratio, gap, bottleneck_flag.
    """
    cap_long = compute_recruiter_capacity(recruiters)
    cap_agg = aggregate_capacity(cap_long)

    out = forecast_df.merge(
        cap_agg,
        on=["business_unit", "skill_family"],
        how="left",
    ).fillna({"monthly_capacity": 0, "recruiter_count": 0})

    # Clearance haircut
    if positions is not None:
        clearance_mix = (
            positions.groupby(["business_unit", "skill_family", "clearance_type"])
            .size()
            .reset_index(name="req_count")
        )
        # Weighted-average TTF multiplier per (BU, SF):
        clearance_mix["ttf_mult"] = clearance_mix["clearance_type"].map(
            CLEARANCE_TTF_MULTIPLIER
        )
        weighted = (
            clearance_mix.assign(weighted=lambda d: d["req_count"] * d["ttf_mult"])
            .groupby(["business_unit", "skill_family"])
            .apply(
                lambda d: d["weighted"].sum() / d["req_count"].sum()
                if d["req_count"].sum() > 0 else 1.0,
                include_groups=False,
            )
            .reset_index(name="clearance_weighted_ttf")
        )
        out = out.merge(weighted, on=["business_unit", "skill_family"], how="left")
        out["clearance_weighted_ttf"] = out["clearance_weighted_ttf"].fillna(1.0)
        out["effective_capacity"] = out["monthly_capacity"] / out["clearance_weighted_ttf"]
    else:
        out["clearance_weighted_ttf"] = 1.0
        out["effective_capacity"] = out["monthly_capacity"]

    # Avoid div-by-zero for coverage ratio
    out["coverage_ratio"] = np.where(
        out["forecast"] > 0,
        out["effective_capacity"] / out["forecast"],
        np.nan,
    )
    out["gap"] = out["forecast"] - out["effective_capacity"]
    out["bottleneck_flag"] = np.where(
        out["coverage_ratio"] < 0.85,
        "Bottleneck",
        np.where(out["coverage_ratio"] < 1.0, "Tight", "Covered"),
    )
    # Round for readability
    for col in ["monthly_capacity", "effective_capacity", "coverage_ratio",
                "gap", "clearance_weighted_ttf"]:
        out[col] = out[col].round(2)
    return out


def rollup_bottlenecks(coverage: pd.DataFrame) -> pd.DataFrame:
    """Summary of bottleneck severity across the planning horizon."""
    bot = coverage[coverage["bottleneck_flag"] == "Bottleneck"]
    summary = (
        bot.groupby(["business_unit", "skill_family"])
        .agg(
            months_in_bottleneck=("month", "nunique"),
            avg_coverage_ratio=("coverage_ratio", "mean"),
            total_gap_hires=("gap", "sum"),
        )
        .reset_index()
        .sort_values("total_gap_hires", ascending=False)
        .round(2)
    )
    return summary


if __name__ == "__main__":
    from src.forecast import ForecastConfig, forecast_demand
    from src.generate import ScenarioConfig, generate_all

    hist, positions, recruiters = generate_all(ScenarioConfig())
    fc = forecast_demand(hist, positions, ForecastConfig(scenario="Growth"))
    coverage = compute_coverage(fc, recruiters, positions)
    print("Sample coverage rows:")
    print(coverage.head(10))
    print("\nTop bottlenecks:")
    print(rollup_bottlenecks(coverage).head(10))
