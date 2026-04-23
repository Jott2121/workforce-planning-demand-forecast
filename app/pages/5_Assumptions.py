"""Transparent assumptions panel."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.schema import (  # noqa: E402
    CLEARANCE_TTF_MULTIPLIER,
    DEFAULT_RECRUITER_THROUGHPUT,
)

st.set_page_config(page_title="Assumptions", page_icon="🔍", layout="wide")

st.title("Assumptions")
st.caption(
    "Every workforce plan depends on parameters that are easy to forget "
    "once the charts look polished. This page makes them explicit so they "
    "can be reviewed, challenged, and updated."
)

# -----------------------------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Recruiter throughput (hires / recruiter / month)")
    tp_df = pd.DataFrame(
        sorted(DEFAULT_RECRUITER_THROUGHPUT.items()),
        columns=["Skill family", "Baseline throughput"],
    )
    st.dataframe(tp_df, use_container_width=True, hide_index=True)
    st.caption(
        "Default assumptions. A real deployment should calibrate these per "
        "recruiter team using the trailing 12 months of actuals."
    )

with col_b:
    st.subheader("Clearance time-to-fill multipliers")
    clr_df = pd.DataFrame(
        sorted(CLEARANCE_TTF_MULTIPLIER.items()),
        columns=["Clearance type", "TTF multiplier"],
    )
    clr_df["TTF multiplier"] = clr_df["TTF multiplier"].apply(lambda v: f"{v:.2f}x")
    st.dataframe(clr_df, use_container_width=True, hide_index=True)
    st.caption(
        "Illustrative; sourced from ClearanceJobs / SHRM / Deltek GovWin "
        "2022–2024 industry benchmarks. Defense-industry deployments would "
        "update these against their own fill-time actuals by clearance level."
    )

st.divider()

st.subheader("Secondary skill family coverage factor")
st.markdown(
    """
When a recruiter is listed with a secondary skill family, we attribute
**35 %** of their monthly capacity to that skill family rather than 100 %.
This models the real-world overhead of context-switching between role
types. The factor is configurable in `src/capacity.py` (`SECONDARY_COVERAGE_FACTOR`).

Production deployments should calibrate this against the recruiter team's
observed dual-coverage outcomes over the last 4–6 quarters.
    """
)

st.divider()

st.subheader("Scenario multipliers")
st.markdown(
    """
| Scenario | Demand multiplier | Notes |
|---|---|---|
| Base | 1.00 | Current plan of record |
| Growth | 1.25 | Program-win / headcount-expansion case |
| Flat | 0.90 | Freeze on non-critical reqs |
| Constrained | 0.70 | CR / appropriations-driven slowdown |

Scenarios are deliberately simple multipliers for demo clarity. Production
versions would layer in program-level hiring ramps, scheduled separations,
and internal-transfer intake as first-class inputs.
    """
)

st.divider()

st.subheader("Data provenance")
st.markdown(
    """
- **Historical fills** → ATS Applications table + HRIS Worker table (converted applicants)
- **Open / planned positions** → Workday Job_Requisition + workforce plan (Adaptive / Anaplan)
- **Recruiter roster + throughput** → ATS user records + recruiter-operations reporting

All simulated data in this repo is calibrated against published benchmarks
(Talent Board, SHRM, ClearanceJobs, Deltek GovWin, LinkedIn Talent Insights)
and is clearly labeled as synthetic in every chart and export.
    """
)
