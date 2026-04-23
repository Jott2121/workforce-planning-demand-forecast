"""Executive summary generator.

Produces a concise narrative summary of a workforce plan scenario for
HR / TA leadership consumption. The summary is template-based rather than
LLM-generated because the output is structured, regulated, and needs to be
deterministic — three properties that template systems deliver reliably and
that LLMs handle poorly without extensive guardrails.

The module is intentionally designed so a later version could swap in an
LLM-based generator behind the same interface. The calling code in
`app/pages/4_Executive_Summary.py` treats this as an opaque "summary
service" — it does not depend on the backend.

A real enterprise deployment would likely use a hybrid approach: structured
templates for compliance-sensitive outputs, LLM rewriting only for tone and
final polish, with explicit human-in-the-loop review before distribution.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.capacity import rollup_bottlenecks
from src.forecast import roll_up_by_month


@dataclass
class SummaryInputs:
    """Bundle of all data the summary generator needs."""

    scenario: str
    forecast_df: pd.DataFrame
    coverage_df: pd.DataFrame
    recruiter_count: int


def _format_int(n: float | int) -> str:
    return f"{int(round(n)):,}"


def _top_bottleneck_lines(coverage: pd.DataFrame, n: int = 3) -> list[str]:
    top = rollup_bottlenecks(coverage).head(n)
    lines = []
    for _, row in top.iterrows():
        lines.append(
            f"- **{row['business_unit']} / {row['skill_family']}** — "
            f"{int(row['months_in_bottleneck'])} months in bottleneck, "
            f"coverage {row['avg_coverage_ratio']:.0%}, "
            f"~{_format_int(row['total_gap_hires'])} hires short of plan."
        )
    return lines


def _month_range(forecast_df: pd.DataFrame) -> tuple[str, str]:
    return forecast_df["month"].min(), forecast_df["month"].max()


def generate(inputs: SummaryInputs) -> str:
    """Return a markdown executive summary."""
    monthly = roll_up_by_month(inputs.forecast_df)
    total_hires = monthly["forecast"].sum()
    total_planned = monthly["planned_hires"].sum()
    peak_month = monthly.loc[monthly["forecast"].idxmax()]
    start, end = _month_range(inputs.forecast_df)

    n_bottleneck_segments = (
        inputs.coverage_df[inputs.coverage_df["bottleneck_flag"] == "Bottleneck"]
        .groupby(["business_unit", "skill_family"])
        .ngroups
    )
    total_gap = inputs.coverage_df[inputs.coverage_df["gap"] > 0]["gap"].sum()

    scenario_context = {
        "Base": "holds current hiring velocity and priorities steady",
        "Growth": "reflects accelerated hiring tied to program wins and headcount expansion",
        "Flat": "assumes hiring freezes on non-critical reqs while protecting core programs",
        "Constrained": (
            "models a significant hiring slowdown — typical of CR / appropriations "
            "uncertainty or post-award spend discipline"
        ),
    }.get(inputs.scenario, "")

    top_lines = _top_bottleneck_lines(inputs.coverage_df, n=3)
    top_block = "\n".join(top_lines) if top_lines else "- No material bottlenecks detected at the (BU, skill family) level."

    md = f"""## Executive Summary — {inputs.scenario} Scenario

**Planning window:** {start} to {end}

This plan {scenario_context}. Under these assumptions, total forecasted hiring
demand across the enterprise is **{_format_int(total_hires)} hires**, against
a stated HR business-partner hiring plan of **{_format_int(total_planned)} positions**.
Peak demand falls in **{peak_month['month']}** at approximately **{_format_int(peak_month['forecast'])} hires**.

Recruiter roster: **{inputs.recruiter_count} recruiters** modeled with average
throughput and skill-family coverage assumptions — see the Assumptions panel
for detail.

### Capacity posture

{"**" + str(n_bottleneck_segments) + " (BU × skill family) segments** are projected to operate as bottlenecks under this scenario," if n_bottleneck_segments else "No segment-level bottlenecks are projected under this scenario."} {"representing a cumulative gap of roughly **" + _format_int(total_gap) + "** hires below plan across the 12-month horizon." if total_gap > 0 else ""}

### Top attention areas

{top_block}

### Recommended next steps

1. **Reallocate or expand recruiter coverage** for the segments above. Cross-
   training existing recruiters on adjacent skill families is typically
   cheaper and faster than net new recruiter headcount.
2. **Review cleared-role assumptions** — clearance-weighted time-to-fill
   drives effective capacity materially below nominal throughput in defense
   and regulated industries. If the clearance mix tightens further, expect
   the gap to widen non-linearly.
3. **Pressure-test the hiring plan with program and business-unit leaders**
   before committing. The forecast blends historical patterns with the
   stated plan; segments where plan >> history signal aggressive stretch.
4. **Revisit this forecast quarterly** (monthly for critical segments).
   Source-system drift, recruiter turnover, and program scope changes make
   a static annual plan stale within one quarter.

*Summary generated deterministically from the current scenario inputs. Decision
support only — final hiring decisions require HR business partner, finance,
and program-leadership approval per company policy.*
"""
    return md


if __name__ == "__main__":
    from src.capacity import compute_coverage
    from src.forecast import ForecastConfig, forecast_demand
    from src.generate import ScenarioConfig, generate_all

    hist, pos, rec = generate_all(ScenarioConfig())
    fc = forecast_demand(hist, pos, ForecastConfig(scenario="Growth"))
    cov = compute_coverage(fc, rec, pos)
    summary = generate(
        SummaryInputs(
            scenario="Growth",
            forecast_df=fc,
            coverage_df=cov,
            recruiter_count=len(rec),
        )
    )
    print(summary)
