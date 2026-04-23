"""Forecast charts and capacity heatmap."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.forecast import roll_up_by_month  # noqa: E402

st.set_page_config(
    page_title="Forecast & Capacity",
    page_icon="📈",
    layout="wide",
)

if "forecast" not in st.session_state:
    st.warning("Open the Home page first to configure the plan.")
    st.stop()

forecast = st.session_state["forecast"]
coverage = st.session_state["coverage"]
scenario = st.session_state["scenario"]

st.title("Forecast & Capacity")
st.caption(
    "Monthly hiring demand forecast with a confidence band, and recruiter "
    "capacity coverage by (business unit × skill family)."
)

# ---- Enterprise-wide forecast chart ----
st.subheader(f"Enterprise demand forecast — {scenario} scenario")
monthly = roll_up_by_month(forecast)
if len(monthly):
    chart_df = monthly.set_index("month")[
        ["forecast_lower", "forecast", "forecast_upper", "planned_hires"]
    ]
    chart_df.columns = ["Lower (-15%)", "Forecast", "Upper (+15%)", "HR plan"]
    st.line_chart(chart_df, use_container_width=True)
    st.caption(
        "Confidence band is ±15% around the point forecast — illustrative "
        "only. Production versions would use bootstrap or model-native CIs."
    )

st.divider()

# ---- Forecast table ----
st.subheader("Forecast detail")
st.dataframe(
    forecast.style.format(
        {
            "baseline_forecast": "{:.1f}",
            "forecast": "{:.1f}",
            "forecast_lower": "{:.1f}",
            "forecast_upper": "{:.1f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
    height=300,
)

st.divider()

# ---- Capacity heatmap: coverage_ratio by (BU, skill_family) averaged across horizon ----
st.subheader("Recruiter coverage heatmap")
st.caption(
    "Average coverage ratio = (recruiter capacity / forecasted demand) "
    "across the planning horizon. < 85% is flagged as a bottleneck."
)

heatmap = (
    coverage.groupby(["business_unit", "skill_family"])["coverage_ratio"]
    .mean()
    .reset_index()
    .pivot(index="business_unit", columns="skill_family", values="coverage_ratio")
)

if not heatmap.empty:
    # Style and display.
    styled = heatmap.style.format("{:.2f}").background_gradient(
        cmap="RdYlGn", vmin=0.5, vmax=1.5, axis=None
    )
    st.dataframe(styled, use_container_width=True)
    st.caption(
        "Green = covered. Yellow = tight. Red = bottleneck. Cells with "
        "`nan` had no forecasted demand in this scenario / filter set."
    )

st.divider()

# ---- Coverage detail ----
st.subheader("Segment detail (by month)")
cols = [
    "month", "business_unit", "skill_family",
    "forecast", "monthly_capacity", "effective_capacity",
    "clearance_weighted_ttf", "coverage_ratio", "gap", "bottleneck_flag",
]
st.dataframe(
    coverage[cols].style.format({
        "forecast": "{:.1f}",
        "monthly_capacity": "{:.1f}",
        "effective_capacity": "{:.1f}",
        "clearance_weighted_ttf": "{:.2f}",
        "coverage_ratio": "{:.0%}",
        "gap": "{:+.1f}",
    }).background_gradient(
        subset=["coverage_ratio"], cmap="RdYlGn", vmin=0.5, vmax=1.5
    ),
    use_container_width=True,
    hide_index=True,
    height=400,
)

st.download_button(
    label="Download forecast + capacity detail (CSV)",
    data=coverage.to_csv(index=False).encode("utf-8"),
    file_name=f"workforce_plan_{scenario.lower()}.csv",
    mime="text/csv",
)
