"""Workforce Planning & Recruiter Capacity — decision support dashboard.

Multi-page Streamlit app:

    Home (this file)                    — Enterprise posture + KPIs
    1_Forecast_&_Capacity.py            — Forecast charts, capacity heatmap
    2_Bottlenecks.py                    — Ranked bottleneck list, detail table
    3_Scenario_Comparison.py            — Side-by-side scenarios
    4_Executive_Summary.py              — Narrative summary for leadership
    5_Assumptions.py                    — Transparent model parameters

Run:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.capacity import compute_coverage  # noqa: E402
from src.forecast import ForecastConfig, forecast_demand, roll_up_by_month  # noqa: E402
from src.generate import ScenarioConfig, generate_all  # noqa: E402
from src.schema import (  # noqa: E402
    BUSINESS_UNITS,
    CLEARANCE_TYPES,
    LOCATIONS,
    SKILL_FAMILIES,
)

st.set_page_config(
    page_title="Workforce Planning & Capacity",
    page_icon="📐",
    layout="wide",
)


# -----------------------------------------------------------------------------
# Shared data loaders (cached; sub-pages read from session_state)
# -----------------------------------------------------------------------------


@st.cache_data
def _load_workforce(seed: int, horizon: int, volume: int, growth: float):
    config = ScenarioConfig(
        seed=seed,
        planning_horizon_months=horizon,
        annual_hiring_volume=volume,
        growth_rate=growth,
    )
    return generate_all(config)


@st.cache_data
def _build_forecast(
    scenario: str,
    horizon: int,
    historical_csv: str,
    positions_csv: str,
) -> pd.DataFrame:
    """Rebuild the forecast when any input changes.

    Note: we pass the dataframes as CSV strings so `@st.cache_data` can hash
    them — it does not hash DataFrames directly.
    """
    hist = pd.read_csv(pd.io.common.StringIO(historical_csv))
    pos = pd.read_csv(pd.io.common.StringIO(positions_csv))
    return forecast_demand(
        hist, pos, ForecastConfig(scenario=scenario, horizon_months=horizon)
    )


# -----------------------------------------------------------------------------
# Sidebar: enterprise controls
# -----------------------------------------------------------------------------


st.sidebar.title("Workforce Plan")
st.sidebar.caption(
    "Configure the planning scenario. In production, these inputs would be "
    "sourced from Workday, the ATS, and recruiter-operations reporting."
)

with st.sidebar.expander("Scenario", expanded=True):
    scenario = st.selectbox(
        "Scenario",
        options=["Base", "Growth", "Flat", "Constrained"],
        index=0,
        help=(
            "Base = current hiring velocity. Growth = +25% demand. "
            "Flat = -10%. Constrained = -30% (CR / appropriations risk)."
        ),
    )
    horizon_months = st.slider(
        "Planning horizon (months)", min_value=6, max_value=24, value=12
    )

with st.sidebar.expander("Enterprise parameters", expanded=False):
    annual_volume = st.number_input(
        "Baseline annual hiring volume",
        min_value=100,
        max_value=20_000,
        value=1200,
        step=100,
    )
    growth_rate = st.slider(
        "YoY demand growth rate", min_value=-0.15, max_value=0.25, value=0.05, step=0.01
    )
    seed = st.number_input("Random seed (reproducibility)", 1, 9999, 42)

with st.sidebar.expander("Filters", expanded=False):
    selected_bus = st.multiselect("Business unit", BUSINESS_UNITS, default=BUSINESS_UNITS)
    selected_families = st.multiselect(
        "Skill family", SKILL_FAMILIES, default=SKILL_FAMILIES
    )

# Pull workforce data.
historical, positions, recruiters = _load_workforce(
    int(seed), int(horizon_months), int(annual_volume), float(growth_rate)
)
forecast = _build_forecast(
    scenario,
    int(horizon_months),
    historical.to_csv(index=False),
    positions.to_csv(index=False),
)
coverage = compute_coverage(forecast, recruiters, positions)

# Apply filters.
forecast_f = forecast[
    forecast["business_unit"].isin(selected_bus)
    & forecast["skill_family"].isin(selected_families)
]
coverage_f = coverage[
    coverage["business_unit"].isin(selected_bus)
    & coverage["skill_family"].isin(selected_families)
]
positions_f = positions[
    positions["business_unit"].isin(selected_bus)
    & positions["skill_family"].isin(selected_families)
]

# Persist for sub-pages.
st.session_state["scenario"] = scenario
st.session_state["horizon_months"] = horizon_months
st.session_state["historical"] = historical
st.session_state["positions"] = positions_f
st.session_state["recruiters"] = recruiters
st.session_state["forecast"] = forecast_f
st.session_state["coverage"] = coverage_f


# -----------------------------------------------------------------------------
# Home page content
# -----------------------------------------------------------------------------


st.title("📐 Workforce Planning & Recruiter Capacity")
st.caption(
    "Strategic workforce planning, recruiter capacity forecasting, and "
    "scenario-based hiring strategy — decision support for enterprise "
    "talent organizations."
)

# KPI strip
monthly = roll_up_by_month(forecast_f) if len(forecast_f) else pd.DataFrame()
total_demand = int(monthly["forecast"].sum()) if len(monthly) else 0
total_planned = int(monthly["planned_hires"].sum()) if len(monthly) else 0
n_bottleneck = int(
    coverage_f[coverage_f["bottleneck_flag"] == "Bottleneck"]
    .groupby(["business_unit", "skill_family"])
    .ngroups
)
total_gap = int(coverage_f[coverage_f["gap"] > 0]["gap"].sum()) if len(coverage_f) else 0
n_recruiters = len(recruiters)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Scenario", scenario)
c2.metric("Forecasted hires", f"{total_demand:,}", f"plan: {total_planned:,}")
c3.metric("Recruiter roster", f"{n_recruiters}")
c4.metric("Bottleneck segments", f"{n_bottleneck}")
c5.metric("Cumulative gap", f"{total_gap:,} hires")

st.divider()

# Landing copy + navigation hints
left, right = st.columns((2, 1))
with left:
    st.subheader("What this app does")
    st.markdown(
        """
This dashboard supports enterprise workforce planning decisions across the
next 6 to 24 months.

| Page | Purpose |
|---|---|
| **1. Forecast & Capacity** | Monthly demand forecast with confidence bands + recruiter capacity heatmap |
| **2. Bottlenecks** | Ranked list of under-covered (BU × skill family) segments with detail drilldown |
| **3. Scenario Comparison** | Side-by-side comparison of Base / Growth / Flat / Constrained scenarios |
| **4. Executive Summary** | Auto-generated narrative summary suitable for leadership review |
| **5. Assumptions** | Transparent view of every model parameter and assumption |

Adjust the scenario, horizon, and filters in the sidebar — all pages update
live.
        """
    )

with right:
    st.subheader("Quick enterprise-wide view")
    if len(monthly):
        monthly_display = monthly.set_index("month")[
            ["planned_hires", "forecast"]
        ].rename(
            columns={
                "planned_hires": "Planned (HR plan)",
                "forecast": "Forecast",
            }
        )
        st.line_chart(monthly_display, use_container_width=True)
        st.caption("Planned hires vs model forecast, enterprise-wide")
    else:
        st.info("No data after current filter set. Expand filters in the sidebar.")

st.divider()

# Scenario reminder
st.subheader("Scenario context")
context = {
    "Base": (
        "Assumes current hiring velocity, priorities, and clearance mix hold steady. "
        "This is the default plan-of-record view."
    ),
    "Growth": (
        "Accelerated hiring aligned with program wins and headcount expansion. "
        "+25% demand uplift across the horizon. Tests whether current recruiter "
        "capacity can sustain growth without expanding the team."
    ),
    "Flat": (
        "Hiring freeze on non-critical requisitions while protecting core programs. "
        "-10% demand. Useful for modeling efficiency scenarios or post-reorganization states."
    ),
    "Constrained": (
        "Significant slowdown — typical of continuing-resolution / appropriations "
        "uncertainty, or post-award spend discipline. -30% demand. "
        "Supports discussion around recruiter deployment during a downturn."
    ),
}
st.info(context[scenario])

st.divider()
st.caption(
    "Data: simulated to approximate a mid-sized defense / aerospace business "
    "unit. Production deployments replace the simulator with Workday + ATS + "
    "recruiter operations feeds. See the Assumptions page for full detail."
)
