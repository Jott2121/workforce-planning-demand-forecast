"""Executive summary for HR / TA leadership."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.executive_summary import SummaryInputs, generate  # noqa: E402

st.set_page_config(page_title="Executive Summary", page_icon="📝", layout="wide")

if "coverage" not in st.session_state:
    st.warning("Open the Home page first to configure the plan.")
    st.stop()

scenario = st.session_state["scenario"]
forecast = st.session_state["forecast"]
coverage = st.session_state["coverage"]
recruiters = st.session_state["recruiters"]

st.title("Executive Summary")
st.caption(
    "Auto-generated narrative summary of the current scenario, sized for "
    "CHRO / TA leadership consumption. Summary is deterministic and based "
    "entirely on the current inputs — not LLM-generated — so it is "
    "reproducible and defensible in governance review."
)

summary = generate(
    SummaryInputs(
        scenario=scenario,
        forecast_df=forecast,
        coverage_df=coverage,
        recruiter_count=len(recruiters),
    )
)
st.markdown(summary)

st.divider()

st.download_button(
    label="Download summary (Markdown)",
    data=summary.encode("utf-8"),
    file_name=f"workforce_plan_summary_{scenario.lower()}.md",
    mime="text/markdown",
)

st.markdown(
    """
---

### A note on LLM vs template summaries

Production workforce-planning narratives are typically better served by
structured templates than by LLM generation — outputs need to be
*reproducible* (the same scenario should always produce the same summary
for audit purposes), *defensible* (every number traceable to source data),
and *compliant* (careful about what is said, and not said, about
individuals or groups).

A realistic enterprise deployment could use an LLM for a final
tone-and-polish pass over this template output, but the numerical and
structural content should remain deterministic. This repo's summary is
purely template-based.
    """
)
