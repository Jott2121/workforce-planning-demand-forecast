# Workforce Planning & Recruiter Capacity

![CI](https://github.com/Jott2121/workforce-planning-demand-forecast/actions/workflows/ci.yml/badge.svg)

Strategic workforce planning, recruiter capacity forecasting, and scenario-based hiring strategy — decision support for enterprise talent organizations.

**Live dashboard:** deployment URL to be added. Run locally with `streamlit run app/streamlit_app.py`.

---

## What this project does

Modern workforce planning asks three questions every quarter:

1. **How many hires will each business unit need over the next 6 to 24 months?**
2. **Does our recruiter roster have the capacity to deliver that plan?**
3. **Where are the bottlenecks, and how do they shift if the business plan tightens or expands?**

This application answers those questions against realistic enterprise HR and recruiting data, produces a ranked list of bottleneck segments, supports side-by-side scenario comparison, and generates an executive-ready narrative summary for leadership review.

The dashboard is intentionally structured around how an enterprise People Analytics team would operate: transparent assumptions, segment-level accountability, scenario pressure-testing, and human-in-the-loop interpretation — not black-box recommendations.

---

## Dashboard

A five-page Streamlit application:

| Page | Purpose |
|---|---|
| **Home** | KPI strip, enterprise-wide demand trajectory, scenario context |
| **Forecast & Capacity** | Monthly forecast with confidence bands, coverage heatmap by (business unit × skill family), segment detail table with export |
| **Bottlenecks** | Ranked bottleneck list, segment drilldown, forecast-vs-capacity chart |
| **Scenario Comparison** | Side-by-side Base / Growth / Flat / Constrained scenarios with delta table |
| **Executive Summary** | Auto-generated narrative for leadership review, markdown export |
| **Assumptions** | Transparent recruiter throughput, clearance multipliers, scenario definitions, data provenance |

---

## Data

Simulated enterprise HR / recruiting data calibrated against published industry benchmarks. Three core tables mirror the shape of what a real deployment would read from source systems.

### Tables

**`historical_fills`** (~2,200 rows over 24 months)

| Column | Notes |
|---|---|
| hire_month | ISO yyyy-mm |
| business_unit | Aeronautics / Missiles & Fire Control / Rotary & Mission Systems / Space / Corporate Shared Services |
| location | 7 locations + Remote-Eligible |
| skill_family | 12 skill families spanning engineering, operations, functional |
| clearance_type | None / Public Trust / Secret / Top Secret / TS/SCI |
| days_to_fill | Clearance-weighted time-to-fill |

**`positions`** (~1,200 rows over the planning horizon)

Open and planned requisitions from the workforce plan. Requisition ID, business unit, location, skill family, job level (1–6), clearance type, planned start month, priority.

**`recruiters`** (~40 rows)

Recruiter ID, name, business unit, primary skill family, secondary skill families, monthly throughput, and allocation percentage.

### Calibration sources

- **Defense hiring volume patterns** (2–4 % YoY, 8–15 % attrition)
- **Cleared-role time-to-fill** (ClearanceJobs, SHRM, Deltek GovWin 2022–2024)
- **Recruiter throughput ranges** (1.5 to 4 hires per recruiter per month, published industry reports)

All simulated data is clearly labeled as synthetic in every chart and export. The simulator is reproducible (`seed=42` by default) and tunable via `src.generate.ScenarioConfig`.

---

## Methodology

### Demand forecast

For each (business unit × skill family) series, the baseline forecast is a decomposition of the last 24 months of historical fills into:

- **Level** (median monthly hires across the trailing period)
- **Seasonality** (Q1 / Q3 hiring pickups, Q4 holiday dip — amplitude ±20 %)
- **Trend** (linear regression slope per series)

That baseline is then **blended with the explicit hiring plan** from Workday / Adaptive / Anaplan. For any (month × BU × skill family) slice, the forecast is the greater of the scenario-scaled baseline and the stated plan — respecting HR business partner input while flagging cases where the plan materially exceeds historical pattern.

Scenario multipliers apply uniformly across all segments:

| Scenario | Multiplier | Intent |
|---|---:|---|
| Growth | 1.25 | Program-win / headcount expansion |
| Base | 1.00 | Current plan of record |
| Flat | 0.90 | Freeze on non-critical requisitions |
| Constrained | 0.70 | Continuing-resolution / appropriations slowdown |

A production version would replace the decomposed baseline with a proper SARIMAX or Prophet fit per series. The current implementation is chosen for transparency and dependency-weight; every forecasted number traces back to visible inputs.

### Recruiter capacity model

For each recruiter:

```
monthly_capacity = throughput_hires_per_month × allocation_pct
```

Coverage attribution to a given skill family:

- **Primary skill family**: 100 % of capacity
- **Secondary skill families**: 35 % of capacity each (models the context-switch overhead of dual coverage)

### Clearance time-to-fill haircut

Cleared requisitions take meaningfully longer to fill than unclassified ones. Since the forecast is in hires rather than requisitions, we apply a weighted time-to-fill multiplier to each segment's nominal capacity:

| Clearance type | TTF multiplier |
|---|---:|
| None | 1.00x |
| Public Trust | 1.15x |
| Secret | 1.35x |
| Top Secret | 1.75x |
| TS/SCI | 2.10x |

The effective capacity for a segment is nominal capacity divided by the weighted-average TTF multiplier for that segment's clearance mix. This is the single assumption cleared-industry planners most under-weight in spreadsheet models.

### Bottleneck thresholds

- **Bottleneck**: coverage ratio < 85 % — meaningful shortfall risk
- **Tight**: 85 %–100 % — technically covered, no buffer for recruiter PTO, turnover, or req surge
- **Covered**: ≥ 100 %

---

## Enterprise deployment

This project is structured as a decision-support tool, not as a production system. The notes below document what would change in a real deployment.

### Source system mapping

| Table here | Production source |
|---|---|
| `historical_fills` | ATS Applications joined with HRIS Worker (converted applicants) — Workday, Greenhouse, Lever, iCIMS |
| `positions` | Workday `Job_Requisition` joined with the workforce plan in Adaptive / Anaplan |
| `recruiters` | ATS user records joined with recruiter-operations reporting for trailing-90-day throughput |

Skill family is rarely a native HRIS field — it is typically derived from a curated job-architecture mapping that talent acquisition maintains. Location should be resolved to a canonical list (not free text) before joining.

### Data quality

Before any forecast is produced, the pipeline should enforce:

- **Required fields non-null** on business unit, skill family, clearance type, and planned start month
- **Duplicate detection** on requisition ID (Workday occasionally emits duplicate reqs across integration refreshes)
- **Business-unit canonicalization** — merging subsidiary and historical BU names
- **Skill family mapping completeness** — any req with an unmapped job code is quarantined, not silently bucketed
- **Date validity** — planned start month must be within the configured planning horizon
- **Outlier handling on days-to-fill** — fills under 14 days or over 365 days are excluded from baseline computation (typically indicative of data-entry errors or offline conversions)

Refresh cadence: a daily overnight batch is typical for a dashboard used in weekly TA leadership meetings; real-time feeds are rarely necessary for planning work.

### Governance and security

- **Role-based access**: HR Business Partners see only their business unit; TA leaders see their portfolio; People Analytics analysts see enterprise-wide; executives see aggregate only. Recruiter-level capacity is visible to the recruiter's manager and the recruiter themselves.
- **No PII in forecast outputs**: segment-level aggregates only. Employee names appear only in the recruiter roster, never in forecast or bottleneck tables.
- **Auditability**: every exported forecast records the scenario, seed, source-system refresh timestamp, and user who generated it.
- **Appropriate-use guardrail**: this system is for hiring *planning*. It is not a performance-management tool for recruiters. Throughput metrics are averages across a team, not inputs to individual performance reviews.

### Legal and ethics review

Workforce planning is lower-risk than compensation or attrition modeling, but two review points matter:

1. **Clearance-driven capacity adjustments** should be documented and reviewed to ensure the resulting hiring plan does not produce discriminatory allocation of cleared-role opportunities.
2. **Scenario-driven layoff modeling** is out of scope for this project. If this tool is ever adapted to model separations rather than hires, it needs explicit legal review before any deployment.

### Model monitoring

- **Drift**: compare forecasted vs actual hires monthly; flag any (BU, skill family) segment where residuals exceed ±20 % for two consecutive months.
- **Recalibration**: recruiter throughput assumptions should be refreshed quarterly against actual trailing-90-day performance.
- **Clearance mix tracking**: if the clearance mix of forward requisitions shifts materially, the capacity haircut will materially shift; alert when any BU's clearance mix moves more than 10 pp in either direction.
- **Change logging**: every change to a scenario multiplier, throughput assumption, or skill-family mapping is logged with the analyst who made it and a justification.

### User roles

| Role | Primary use |
|---|---|
| HR Business Partners | See their BU's plan, pressure-test with program leaders, escalate bottlenecks |
| Recruiting leaders | Compare segments across the portfolio, plan team-level coverage |
| People Analytics | Maintain the model, investigate drift, support scenario discussions |
| TA operations | Monitor throughput assumptions, feed capacity actuals back |
| Compensation partners | Cross-reference cleared-role gap with comp band pressure |
| Executives | Consume the executive-summary page; approve cross-portfolio reallocation decisions |

---

## Repository layout

```
workforce-planning-demand-forecast/
├── src/
│   ├── schema.py            — Data schema + constants (BUs, locations, skill families, clearances)
│   ├── generate.py          — Mock data generator with ScenarioConfig
│   ├── forecast.py          — Demand forecast with scenario multipliers
│   ├── capacity.py          — Recruiter capacity + bottleneck detection
│   └── executive_summary.py — Template-based summary generator
├── app/
│   ├── streamlit_app.py     — Home page
│   └── pages/               — Forecast, Bottlenecks, Scenarios, Exec Summary, Assumptions
├── tests/                   — Unit tests (14 tests, all passing)
├── data/                    — Generated CSVs (reproducible from src.generate)
├── docs/                    — Supporting documentation
├── .github/workflows/ci.yml — Lint + test on push
├── requirements.txt
└── README.md
```

---

## Run it

```bash
pip install -r requirements.txt
python -m src.generate              # generate the data fixture
streamlit run app/streamlit_app.py  # launch dashboard
pytest tests/                       # run unit tests
```

---

## About the simulated data

Every chart in the application is produced from synthetic data calibrated against published industry benchmarks. Simulation is the right choice for a public demonstration of workforce-planning methodology: real workforce plans are proprietary, and no public dataset contains the necessary combination of business-unit, skill-family, clearance, and recruiter-roster detail. Simulation also preserves a useful property for verification — for any parameter setting, the forecast and capacity model produce a reproducible, inspectable output that a reviewer can audit end-to-end.

A production deployment replaces `src.generate` with real-source-system feeds. The rest of the codebase is designed to not change.

MIT licensed.
