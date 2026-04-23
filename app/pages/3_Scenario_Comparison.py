"""Side-by-side scenario comparison."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.capacity import compute_coverage  # noqa: E402
from src.forecast import ForecastConfig, forecast_demand, roll_up_by_month  # noqa: E402

st.set_page_config(page_title="Scenario Comparison", page_icon="🔀", layout="wide")

if "historical" not in st.session_state:
    st.warning("Open the Home page first to configure the plan.")
    st.stop()

historical = st.session_state["historical"]
positions = st.session_state["positions"]
recruiters = st.session_state["recruiters"]
horizon = int(st.session_state["horizon_months"])

st.title("Scenario Comparison")
st.caption(
    "Run all four scenarios against the same recruiter roster and hiring "
    "plan. Compare demand, gap, and bottleneck counts side by side."
)

scenarios = ["Base", "Growth", "Flat", "Constrained"]

rows: list[dict] = []
monthly_frames: list[pd.DataFrame] = []
for s in scenarios:
    fc = forecast_demand(
        historical, positions, ForecastConfig(scenario=s, horizon_months=horizon)
    )
    cov = compute_coverage(fc, recruiters, positions)
    total_demand = float(fc["forecast"].sum())
    total_gap = float(cov[cov["gap"] > 0]["gap"].sum())
    n_bottleneck = (
        cov[cov["bottleneck_flag"] == "Bottleneck"]
        .groupby(["business_unit", "skill_family"])
        .ngroups
    )
    rows.append(
        {
            "Scenario": s,
            "Total forecasted hires": round(total_demand),
            "Cumulative gap (hires)": round(total_gap),
            "Bottleneck segments": n_bottleneck,
        }
    )
    monthly = roll_up_by_month(fc)
    monthly["scenario"] = s
    monthly_frames.append(monthly)

summary = pd.DataFrame(rows)
st.dataframe(
    summary.style.format(
        {
            "Total forecasted hires": "{:,}",
            "Cumulative gap (hires)": "{:+,}",
            "Bottleneck segments": "{:,}",
        }
    ).background_gradient(
        subset=["Cumulative gap (hires)", "Bottleneck segments"],
        cmap="Reds",
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

st.subheader("Monthly demand by scenario")
all_monthly = pd.concat(monthly_frames)
pivot = all_monthly.pivot_table(
    index="month", columns="scenario", values="forecast"
)[scenarios]
st.line_chart(pivot, use_container_width=True)

st.divider()

st.markdown(
    """
### How to use this view

- **Planning conversations** — show which scenarios require net-new
  recruiter capacity vs. which can be covered by reallocation alone.
- **Budget discussions** — translate scenario-level gaps into recruiter
  headcount or contingent-labor spend before requesting incremental budget.
- **Program leadership alignment** — the Constrained scenario surfaces
  exactly which programs would be first to feel hiring pressure if an
  appropriations delay materializes.

Scenarios are deliberately simple multipliers on baseline demand. A real
deployment would layer in program-level hiring ramps, scheduled separations,
and internal transfer intake.
    """
)
