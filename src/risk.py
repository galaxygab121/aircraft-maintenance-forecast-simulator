from __future__ import annotations

import pandas as pd


def build_risk_register(
    scheduled_df: pd.DataFrame,
    today: pd.Timestamp,
) -> pd.DataFrame:
    """
    Risk rules (simple + resume-aligned):
    - OVERDUE: due_date < today and not completed (in our sim, scheduled==False or scheduled_date after due_date)
    - MISSED_WINDOW: not scheduled at all
    - LATE_SCHEDULE: scheduled_date > due_date
    - CAPACITY_SHORTFALL: allocated_labor_hours < labor_hours
    """
    df = scheduled_df.copy()
    df["due_date"] = pd.to_datetime(df["due_date"]).dt.normalize()
    df["scheduled_date"] = pd.to_datetime(df["scheduled_date"]).dt.normalize()

    risks = []

    for _, r in df.iterrows():
        due = r["due_date"]
        sched = r["scheduled_date"]
        scheduled = bool(r["scheduled"])
        labor = float(r["labor_hours"])
        allocated = float(r.get("allocated_labor_hours", 0.0))

        # MISSED WINDOW / UNSCHEDULED
        if not scheduled:
            risks.append(
                {
                    "risk_type": "MISSED_WINDOW",
                    "severity": r["criticality"],
                    "aircraft_id": r["aircraft_id"],
                    "fleet_type": r["fleet_type"],
                    "base": r["base"],
                    "task_id": r["task_id"],
                    "task_name": r["task_name"],
                    "due_date": due,
                    "scheduled_date": pd.NaT,
                    "notes": "No available capacity found within maintenance window.",
                }
            )

        # CAPACITY SHORTFALL (partial allocation)
        if allocated + 1e-9 < labor:
            risks.append(
                {
                    "risk_type": "CAPACITY_SHORTFALL",
                    "severity": r["criticality"],
                    "aircraft_id": r["aircraft_id"],
                    "fleet_type": r["fleet_type"],
                    "base": r["base"],
                    "task_id": r["task_id"],
                    "task_name": r["task_name"],
                    "due_date": due,
                    "scheduled_date": sched if scheduled else pd.NaT,
                    "notes": f"Allocated {allocated:.1f} of {labor:.1f} labor hours.",
                }
            )

        # LATE SCHEDULE
        if scheduled and pd.notna(sched) and sched > due:
            risks.append(
                {
                    "risk_type": "LATE_SCHEDULE",
                    "severity": r["criticality"],
                    "aircraft_id": r["aircraft_id"],
                    "fleet_type": r["fleet_type"],
                    "base": r["base"],
                    "task_id": r["task_id"],
                    "task_name": r["task_name"],
                    "due_date": due,
                    "scheduled_date": sched,
                    "notes": "Scheduled after due date (potential disruption to maintenance window).",
                }
            )

        # OVERDUE (as of today)
        if due < today and (not scheduled or (pd.notna(sched) and sched > due)):
            risks.append(
                {
                    "risk_type": "OVERDUE",
                    "severity": r["criticality"],
                    "aircraft_id": r["aircraft_id"],
                    "fleet_type": r["fleet_type"],
                    "base": r["base"],
                    "task_id": r["task_id"],
                    "task_name": r["task_name"],
                    "due_date": due,
                    "scheduled_date": sched if scheduled else pd.NaT,
                    "notes": "Past-due maintenance as of forecast run date.",
                }
            )

    risk_df = pd.DataFrame(risks)
    if not risk_df.empty:
        risk_df = risk_df.sort_values(by=["severity", "risk_type", "due_date"]).reset_index(drop=True)
    return risk_df