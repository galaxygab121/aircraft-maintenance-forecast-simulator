from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd

from .scheduler import CapacityConfig, build_capacity_calendar, schedule_tasks_greedy


@dataclass
class ForecastConfig:
    start_date: date
    horizon_days: int = 120
    # If True, we create "last_done" dates so tasks become due within horizon
    seed_history: bool = True


def _seed_last_done_date(start_date: date, interval_days: int, offset_days: int) -> date:
    """
    Create a plausible last_done date so the next due date falls near the start of the horizon.
    offset_days shifts due dates across aircraft so results aren't identical.
    """
    # last_done = start_date - (interval_days - offset_days)
    return start_date - timedelta(days=max(1, interval_days - offset_days))


def build_forecast(
    fleet_df: pd.DataFrame,
    task_df: pd.DataFrame,
    cfg: ForecastConfig,
) -> pd.DataFrame:
    """
    Creates a forecast table of maintenance tasks due within the horizon.
    Simplified logic: due_date = last_done + interval_days
    """
    start = pd.to_datetime(cfg.start_date).normalize()
    end = start + pd.Timedelta(days=cfg.horizon_days)

    rows = []
    for i, ac in fleet_df.iterrows():
        aircraft_id = ac["aircraft_id"]
        fleet_type = ac["fleet_type"]
        base = ac["base"]

        tasks = task_df[task_df["fleet_type"] == fleet_type].copy()
        if tasks.empty:
            continue

        for j, t in tasks.iterrows():
            interval_days = int(t["interval_days"])
            window_days = int(t["window_days"])

            if cfg.seed_history:
                # spread due dates so each aircraft doesn't hit same day
                offset = (i * 7 + j * 3) % max(2, interval_days)
                last_done = _seed_last_done_date(cfg.start_date, interval_days, offset)
            else:
                last_done = cfg.start_date

            due = pd.to_datetime(last_done + timedelta(days=interval_days)).normalize()

            # only keep items that enter the horizon or are near it (include slightly overdue)
            if due <= end:
                rows.append(
                    {
                        "aircraft_id": aircraft_id,
                        "fleet_type": fleet_type,
                        "base": base,
                        "task_id": t["task_id"],
                        "task_name": t["task_name"],
                        "criticality": t["criticality"],
                        "labor_hours": float(t["labor_hours"]),
                        "interval_days": interval_days,
                        "window_days": window_days,
                        "due_date": due,
                    }
                )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values(by=["due_date", "criticality"]).reset_index(drop=True)
    return df


def run_simulation(
    fleet_df: pd.DataFrame,
    task_df: pd.DataFrame,
    forecast_cfg: ForecastConfig,
    capacity_cfg: CapacityConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    forecast_df = build_forecast(fleet_df, task_df, forecast_cfg)
    if forecast_df.empty:
        return forecast_df, pd.DataFrame()

    bases = sorted(fleet_df["base"].unique().tolist())

    capacity_df = build_capacity_calendar(
        bases=bases,
        start_date=forecast_cfg.start_date,
        horizon_days=capacity_cfg.horizon_days,
        labor_hours_per_day=capacity_cfg.labor_hours_per_day,
    )

    scheduled_df, capacity_updated = schedule_tasks_greedy(forecast_df, capacity_df)
    return scheduled_df, capacity_updated