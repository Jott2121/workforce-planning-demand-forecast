"""Enterprise data schema for workforce planning and recruiter capacity.

This module documents the tables, fields, and joins that a real deployment
would read from the customer's HRIS, ATS, and talent operations systems. The
simulator in `generate.py` produces the same shapes so the forecasting and
capacity logic can be developed and tested end-to-end without a live source
system.

Table / source-system mapping
-----------------------------
- positions            <- HRIS (Workday / Oracle HCM) `Job_Requisition`
- recruiters           <- ATS (Greenhouse / iCIMS / Workday Recruiting) `User`
                         + recruiter operations reporting for throughput
- historical_fills     <- ATS `Application` + HRIS `Worker` for converted fills
- headcount_demand     <- Workforce plan (Adaptive / Anaplan) +
                         HR business partner input
- skill_family_demand  <- Derived from `positions` + talent intelligence feed
                         (LinkedIn Talent Insights, Lightcast, Draup)

Join keys
---------
- business_unit_id is the primary rollup dimension across every table.
- skill_family_id joins requisitions → recruiter coverage → demand forecast.
- location_id enables geographic capacity and clearance-site constraints.
- clearance_type is a first-class dimension because in cleared / regulated
  industries (defense, aerospace, federal) it drives both time-to-fill and
  recruiter throughput assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass

# Dimension constants ---------------------------------------------------------

BUSINESS_UNITS: list[str] = [
    "Aeronautics",
    "Missiles & Fire Control",
    "Rotary & Mission Systems",
    "Space",
    "Corporate Shared Services",
]

LOCATIONS: list[str] = [
    "Fort Worth, TX",
    "Orlando, FL",
    "Grand Prairie, TX",
    "Sunnyvale, CA",
    "Denver, CO",
    "Bethesda, MD",
    "Huntsville, AL",
    "Remote-Eligible",
]

SKILL_FAMILIES: list[str] = [
    "Software Engineering",
    "Systems Engineering",
    "Cybersecurity",
    "Data Science & Analytics",
    "Mechanical Engineering",
    "Electrical Engineering",
    "Program / Project Management",
    "Manufacturing Operations",
    "Supply Chain",
    "HR / People Analytics",
    "Finance & Accounting",
    "Business Development",
]

CLEARANCE_TYPES: list[str] = [
    "None",
    "Public Trust",
    "Secret",
    "Top Secret",
    "TS/SCI",
]

# Clearance premiums: how much additional time-to-fill a cleared requisition
# adds, as a multiplier on the role's baseline time-to-fill. These values are
# illustrative and calibrated against published industry benchmarks
# (ClearanceJobs / SHRM / Deltek GovWin 2022-2024 reports).
CLEARANCE_TTF_MULTIPLIER: dict[str, float] = {
    "None": 1.00,
    "Public Trust": 1.15,
    "Secret": 1.35,
    "Top Secret": 1.75,
    "TS/SCI": 2.10,
}

# Default recruiter throughput assumptions (hires per recruiter per month).
# These are deliberately conservative; a real deployment should calibrate
# these per recruiter team using the last 12 months of actuals.
DEFAULT_RECRUITER_THROUGHPUT: dict[str, float] = {
    "Software Engineering": 3.0,
    "Systems Engineering": 2.2,
    "Cybersecurity": 1.8,
    "Data Science & Analytics": 2.4,
    "Mechanical Engineering": 2.5,
    "Electrical Engineering": 2.3,
    "Program / Project Management": 3.2,
    "Manufacturing Operations": 4.0,
    "Supply Chain": 3.5,
    "HR / People Analytics": 3.0,
    "Finance & Accounting": 3.3,
    "Business Development": 2.0,
}


# Dataclasses for type clarity -----------------------------------------------


@dataclass(frozen=True)
class Position:
    """A single open or planned requisition (maps to Workday Job_Requisition)."""

    requisition_id: str
    business_unit: str
    location: str
    skill_family: str
    job_level: int            # 1 (associate) to 6 (director+)
    clearance_type: str
    planned_start_month: str  # ISO yyyy-mm
    priority: str             # "Critical" / "High" / "Standard"


@dataclass(frozen=True)
class Recruiter:
    """A recruiter's skill-family coverage and capacity.

    Maps to the ATS user record joined with recruiter-operations throughput
    reporting. `throughput_hires_per_month` is a lagging-indicator average
    over the trailing 90 days; capacity planners typically apply a 0.8x
    haircut to this number for forward-looking plans.
    """

    recruiter_id: str
    name: str
    business_unit: str
    primary_skill_family: str
    secondary_skill_families: tuple[str, ...]
    throughput_hires_per_month: float
    allocation_pct: float     # 0.0 - 1.0; part-time, shared, or 100% dedicated
