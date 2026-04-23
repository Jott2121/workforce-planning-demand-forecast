"""Ranked bottleneck list + detail drilldown."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.capacity import rollup_bottlenecks  # noqa: E402

st.set_page_config(page_title="Bottlenecks", page_icon="⚠️", layout="wide")

if "coverage" not in st.session_state:
    st.warning("Open the Home page first to configure the plan.")
    st.stop()

coverage = st.session_state["coverage"]
scenario = st.session_state["scenario"]

st.title("Bottleneck Analysis")
st.caption(
    "Where demand is projected to exceed recruiter capacity — ranked by the "
    "cumulative hiring gap across the planning horizon."
)

summary = rollup_bottlenecks(coverage)

c1, c2, c3 = st.columns(3)
c1.metric("Bottleneck segments", f"{len(summary):,}")
c2.metric(
    "Total gap (hires below plan)",
    f"{int(summary['total_gap_hires'].sum()):,}"
    if len(summary)
    else "0",
)
worst_ratio = summary["avg_coverage_ratio"].min() if len(summary) else None
c3.metric(
    "Worst coverage ratio",
    f"{worst_ratio:.0%}" if worst_ratio is not None else "—",
)

st.divider()

st.subheader(f"Ranked bottleneck list — {scenario} scenario")
if len(summary):
    st.dataframe(
        summary.style.format(
            {
                "avg_coverage_ratio": "{:.0%}",
                "total_gap_hires": "{:+.0f}",
                "months_in_bottleneck": "{:.0f}",
            }
        ).background_gradient(subset=["total_gap_hires"], cmap="Reds"),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("No bottlenecks detected under the current scenario and filters.")

st.divider()

# ---- Drilldown ----
st.subheader("Segment drilldown")
if len(summary):
    bu_options = summary["business_unit"].unique().tolist()
    bu = st.selectbox("Business unit", bu_options)
    sf_options = (
        summary[summary["business_unit"] == bu]["skill_family"].unique().tolist()
    )
    sf = st.selectbox("Skill family", sf_options)

    segment = coverage[
        (coverage["business_unit"] == bu) & (coverage["skill_family"] == sf)
    ].sort_values("month")
    st.dataframe(
        segment[
            [
                "month", "forecast", "effective_capacity", "coverage_ratio",
                "gap", "bottleneck_flag", "clearance_weighted_ttf",
            ]
        ].style.format(
            {
                "forecast": "{:.1f}",
                "effective_capacity": "{:.1f}",
                "coverage_ratio": "{:.0%}",
                "gap": "{:+.1f}",
                "clearance_weighted_ttf": "{:.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    chart = segment.set_index("month")[["forecast", "effective_capacity"]]
    st.line_chart(chart, use_container_width=True)
    st.caption("Forecast vs. effective capacity for the selected segment.")

st.divider()

st.markdown(
    """
### Interpreting this view

- **Bottleneck**: coverage ratio < 85 %. Meaningful shortfall risk. Candidate
  for recruiter reallocation, cross-training, or temporary contracting.
- **Tight**: 85 %–100 %. Plan is technically covered but has no buffer for
  recruiter PTO, turnover, or req surge. Monitor.
- **Covered**: ≥ 100 %. Capacity sufficient under current assumptions.

The `clearance_weighted_ttf` column is the average time-to-fill multiplier
for this segment based on the clearance mix of planned requisitions —
cleared roles take longer, so nominal capacity must be haircut accordingly.
    """
)

st.download_button(
    label="Download bottleneck summary (CSV)",
    data=summary.to_csv(index=False).encode("utf-8"),
    file_name=f"bottlenecks_{scenario.lower()}.csv",
    mime="text/csv",
)
