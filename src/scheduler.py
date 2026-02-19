from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd


@dataclass
class CapacityConfig:
    # labor hours available per base per day
    labor_hours_per_day: float = 80.0
    # plan horizon in days
    horizon_days: int = 120


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def build_capacity_calendar(
    bases: list[str],
    start_date: date,
    horizon_days: int,
    labor_hours_per_day: float,
) -> pd.DataFrame:
    end_date = start_date + timedelta(days=horizon_days)
    rows = []
    for base in bases:
        for d in _daterange(start_date, end_date):
            rows.append(
                {
                    "base": base,
                    "date": pd.to_datetime(d),
                    "capacity_labor_hours": float(labor_hours_per_day),
                    "used_labor_hours": 0.0,
                }
            )
    return pd.DataFrame(rows)


def schedule_tasks_greedy(
    forecast_df: pd.DataFrame,
    capacity_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Greedy scheduler:
    - Sort tasks by due_date ascending, then criticality (High->Low), then labor_hours desc
    - For each task, allocate labor hours on the earliest day within [due_date - window_days, due_date]
      at the aircraft's base with remaining capacity.
    - If not enough capacity across the window, mark unscheduled.
    Returns: (scheduled_df, capacity_df_updated)
    """
    crit_rank = {"High": 0, "Medium": 1, "Low": 2}
    df = forecast_df.copy()

    df["crit_rank"] = df["criticality"].map(lambda x: crit_rank.get(x, 3))
    df = df.sort_values(
        by=["due_date", "crit_rank", "labor_hours"],
        ascending=[True, True, False],
    ).reset_index(drop=True)

    cap = capacity_df.copy()
    cap["remaining_labor_hours"] = cap["capacity_labor_hours"] - cap["used_labor_hours"]

    scheduled_rows = []

    # index for quick lookup
    cap_key = ["base", "date"]
    cap = cap.sort_values(cap_key).reset_index(drop=True)

    cap_index = {(r["base"], r["date"]): i for i, r in cap.iterrows()}

    for _, task in df.iterrows():
        base = task["base"]
        due_date = pd.to_datetime(task["due_date"]).normalize()
        window_days = int(task["window_days"])
        labor_needed = float(task["labor_hours"])

        window_start = due_date - pd.Timedelta(days=window_days)
        window_dates = pd.date_range(window_start, due_date, freq="D")

        allocated = 0.0
        allocations = []

        for d in window_dates:
            key = (base, d)
            if key not in cap_index:
                continue
            idx = cap_index[key]
            remaining = float(cap.at[idx, "remaining_labor_hours"])
            if remaining <= 0:
                continue

            take = min(remaining, labor_needed - allocated)
            if take > 0:
                cap.at[idx, "used_labor_hours"] += take
                cap.at[idx, "remaining_labor_hours"] -= take
                allocated += take
                allocations.append((d, take))

            if allocated >= labor_needed - 1e-9:
                break

        if allocated >= labor_needed - 1e-9:
            # scheduled: choose the last allocation day as scheduled_date
            scheduled_date = allocations[-1][0]
            scheduled_rows.append(
                {
                    **task.to_dict(),
                    "scheduled": True,
                    "scheduled_date": scheduled_date,
                    "scheduled_base": base,
                    "allocated_labor_hours": allocated,
                }
            )
        else:
            scheduled_rows.append(
                {
                    **task.to_dict(),
                    "scheduled": False,
                    "scheduled_date": pd.NaT,
                    "scheduled_base": base,
                    "allocated_labor_hours": allocated,
                }
            )

    scheduled_df = pd.DataFrame(scheduled_rows).drop(columns=["crit_rank"], errors="ignore")
    capacity_updated = cap.drop(columns=["remaining_labor_hours"], errors="ignore")
    return scheduled_df, capacity_updated