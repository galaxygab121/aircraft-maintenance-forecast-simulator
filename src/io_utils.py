from __future__ import annotations

import os
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"


def ensure_reports_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_fleet() -> pd.DataFrame:
    fleet_path = DATA_DIR / "fleet.csv"
    df = pd.read_csv(fleet_path, parse_dates=["in_service_date"])
    return df


def load_task_cards() -> pd.DataFrame:
    task_path = DATA_DIR / "task_cards.csv"
    df = pd.read_csv(task_path)
    return df


def save_report(df: pd.DataFrame, filename: str) -> str:
    ensure_reports_dir()
    out_path = REPORTS_DIR / filename

    # Special handling for risk register
    if filename == "risk_register.csv":
        RISK_COLUMNS = [
            "risk_type",
            "aircraft_id",
            "task_id",
            "due_date",
            "scheduled_date",
            "days_late",
            "details",
        ]

        if df is None or df.empty:
            df = pd.DataFrame(columns=RISK_COLUMNS)
        else:
            df = df.reindex(columns=RISK_COLUMNS)

    df.to_csv(out_path, index=False)
    return str(out_path)