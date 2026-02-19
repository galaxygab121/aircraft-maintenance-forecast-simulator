from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt

from .io_utils import load_fleet, load_task_cards, save_report, ensure_reports_dir, REPORTS_DIR
from .simulator import ForecastConfig, run_simulation
from .scheduler import CapacityConfig
from .risk import build_risk_register


def build_capacity_summary(capacity_df: pd.DataFrame) -> pd.DataFrame:
    df = capacity_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    summary = (
        df.groupby(["base", "date"], as_index=False)
        .agg(
            capacity_labor_hours=("capacity_labor_hours", "sum"),
            used_labor_hours=("used_labor_hours", "sum"),
        )
    )
    summary["utilization_pct"] = (
        (summary["used_labor_hours"] / summary["capacity_labor_hours"]).fillna(0.0) * 100.0
    )
    return summary


def plot_workload(summary_df: pd.DataFrame) -> str:
    ensure_reports_dir()

    daily = (
        summary_df.groupby("date", as_index=False)
        .agg(capacity=("capacity_labor_hours", "sum"), used=("used_labor_hours", "sum"))
        .sort_values("date")
    )

    plt.figure()
    plt.plot(daily["date"], daily["capacity"], label="Capacity (Labor Hours)")
    plt.plot(daily["date"], daily["used"], label="Planned Workload (Labor Hours)")
    plt.xticks(rotation=45)
    plt.xlabel("Date")
    plt.ylabel("Labor Hours")
    plt.title("Maintenance Planning Workload vs Capacity (Forecast Horizon)")
    plt.legend()
    plt.tight_layout()

    out_path = REPORTS_DIR / "workload_vs_capacity.png"
    plt.savefig(out_path, dpi=160)
    plt.close()
    return str(out_path)


def run(
    forecast_start: Optional[str] = None,
    horizon_days: int = 120,
    capacity_multiplier: float = 1.0,
    write_reports: bool = True,
) -> Dict[str, Any]:
    """
    Runs the simulator and writes fresh outputs every time.

    - horizon_days affects how far ahead we plan
    - capacity_multiplier scales daily labor capacity
      (lower values force constraints -> populate risk register)
    """
    # Forecast start date
    today = pd.to_datetime(date.today()).normalize()
    if forecast_start:
        today = pd.to_datetime(forecast_start).normalize()

    # Load inputs
    fleet_df = load_fleet()
    task_df = load_task_cards()

    # Daily capacity model (hours/day per base)
    base_capacity_per_day = 160
    capacity_per_day = max(1, int(base_capacity_per_day * float(capacity_multiplier)))

    forecast_cfg = ForecastConfig(
        start_date=today.date(),
        horizon_days=int(horizon_days),
        seed_history=True,
    )
    capacity_cfg = CapacityConfig(
        labor_hours_per_day=float(capacity_per_day),
        horizon_days=int(horizon_days),
    )

    scheduled_df, capacity_df = run_simulation(fleet_df, task_df, forecast_cfg, capacity_cfg)

    ensure_reports_dir()

    out = {
        "maintenance_plan": str(REPORTS_DIR / "maintenance_plan.csv"),
        "capacity_calendar": str(REPORTS_DIR / "capacity_calendar.csv"),
        "risk_register": str(REPORTS_DIR / "risk_register.csv"),
        "workload_chart": str(REPORTS_DIR / "workload_vs_capacity.png"),
    }

    if not write_reports:
        return out

    # If nothing produced, still write empty files (so Streamlit doesn't crash)
    if scheduled_df.empty:
        pd.DataFrame().to_csv(out["maintenance_plan"], index=False)
        pd.DataFrame().to_csv(out["capacity_calendar"], index=False)
        pd.DataFrame().to_csv(out["risk_register"], index=False)
        # delete chart if exists
        chart_file = Path(out["workload_chart"])
        if chart_file.exists():
            chart_file.unlink()
        return out

    # Write reports
    save_report(scheduled_df, "maintenance_plan.csv")

    capacity_summary = build_capacity_summary(capacity_df)
    save_report(capacity_summary, "capacity_calendar.csv")

    risk_df = build_risk_register(scheduled_df, today=today)
    save_report(risk_df, "risk_register.csv")

    # Force overwrite chart so Streamlit can't keep a stale version
    chart_path = REPORTS_DIR / "workload_vs_capacity.png"
    if chart_path.exists():
        chart_path.unlink()
    plot_workload(capacity_summary)

    return out


def main() -> None:
    # Local CLI run (still works)
    paths = run(horizon_days=120, capacity_multiplier=1.0, write_reports=True)

    print("\n=== Aircraft Maintenance Forecast Simulator ===")
    print(f"Reports:")
    print(f" - {paths['maintenance_plan']}")
    print(f" - {paths['capacity_calendar']}")
    print(f" - {paths['risk_register']}")
    print("Chart:")
    print(f" - {paths['workload_chart']}\n")


if __name__ == "__main__":
    main()