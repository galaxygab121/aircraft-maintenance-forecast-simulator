from __future__ import annotations

from datetime import date
import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path
from datetime import date
from typing import Optional, Dict, Any

from .io_utils import load_fleet, load_task_cards, save_report, ensure_reports_dir, REPORTS_DIR
from .simulator import ForecastConfig, run_simulation
from .scheduler import CapacityConfig
from .risk import build_risk_register

def run(
    forecast_start: Optional[str] = None,
    horizon_days: int = 120,
    capacity_multiplier: float = 1.0,
    write_reports: bool = True,
) -> Dict[str, Any]:
    """
    Runs the simulator and returns paths + (optionally) in-memory data.
    capacity_multiplier < 1.0 forces capacity constraints to demonstrate risks.
    """

    # ✅ Use your existing defaults if you already set these in main()
    # If you already have variables like FORECAST_START / HORIZON_DAYS / CAPACITY_PER_DAY,
    # just apply multiplier to the capacity variable before scheduling.

    # Example pattern:
    base_capacity_per_day = 160
    if capacity_multiplier < 0.5:
        capacity_per_day = 40
    else:
        capacity_per_day = int(base_capacity_per_day * capacity_multiplier)

    # --- START: plug into your existing flow ---
    # The goal: keep your current logic, but parameterize horizon/capacity.

    # IMPORTANT: replace these 3 lines with whatever you already use
    FORECAST_START = forecast_start or str(date.today())
    HORIZON_DAYS = horizon_days

    # If your capacity is defined in code, multiply it here.
    # Example:
    # CAPACITY_PER_DAY = int(CAPACITY_PER_DAY * capacity_multiplier)

    # Then run your existing simulation exactly as you do now.
    # --- END: plug into your existing flow ---

    # Your code currently writes to reports/*. Return those paths:
    reports_dir = Path("reports")
    out = {
        "maintenance_plan": str(reports_dir / "maintenance_plan.csv"),
        "capacity_calendar": str(reports_dir / "capacity_calendar.csv"),
        "risk_register": str(reports_dir / "risk_register.csv"),
        "workload_chart": str(reports_dir / "workload_vs_capacity.png"),
    }
    return out


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

    # total across bases per day (simple view)
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


def main() -> None:
    # "as of" date for forecast run
    today = pd.to_datetime(date.today()).normalize()

    fleet_df = load_fleet()
    task_df = load_task_cards()

    forecast_cfg = ForecastConfig(start_date=today.date(), horizon_days=120, seed_history=True)
        # Capacity tuning (lower multiplier to force risks)
    base_capacity_per_day = 160
    capacity_multiplier = 0.5  # try 0.6 or 0.4 to generate risk flags
    capacity_per_day = float(base_capacity_per_day * capacity_multiplier)
    capacity_cfg = CapacityConfig(labor_hours_per_day=5, horizon_days=120)

    

    scheduled_df, capacity_df = run_simulation(fleet_df, task_df, forecast_cfg, capacity_cfg)

    if scheduled_df.empty:
        print("No tasks were generated in the forecast horizon. Check input data.")
        return

    # Reports
    plan_path = save_report(scheduled_df, "maintenance_plan.csv")

    capacity_summary = build_capacity_summary(capacity_df)
    cap_path = save_report(capacity_summary, "capacity_calendar.csv")

    risk_df = build_risk_register(scheduled_df, today=today)
    risk_path = save_report(risk_df, "risk_register.csv")

    chart_path = plot_workload(capacity_summary)

    # Console output (nice for demos)
    scheduled_rate = (scheduled_df["scheduled"].mean() * 100.0) if len(scheduled_df) else 0.0
    print("\n=== Aircraft Maintenance Forecast Simulator ===")
    print(f"Forecast start: {today.date()} | Horizon: {forecast_cfg.horizon_days} days")
    print(f"Tasks forecasted: {len(scheduled_df)}")
    print(f"Scheduled rate: {scheduled_rate:.1f}%")
    print(f"Reports:")
    print(f" - {plan_path}")
    print(f" - {cap_path}")
    print(f" - {risk_path}")
    print(f"Chart:")
    print(f" - {chart_path}\n")


if __name__ == "__main__":
    main()