import pandas as pd
import streamlit as st
from pathlib import Path
from pandas.errors import EmptyDataError

from src.main import run  # uses the run() function you added

st.set_page_config(page_title="Tech Ops Planning Dashboard", layout="wide")

st.sidebar.header("Scenario Controls")

demo_mode = st.sidebar.checkbox("Demo Mode (force risks)", value=False)

capacity_multiplier = st.sidebar.slider(
    "Capacity multiplier",
    min_value=0.2,
    max_value=1.2,
    value=0.6 if demo_mode else 1.0,
    step=0.05,
)

horizon_days = st.sidebar.slider(
    "Forecast horizon (days)",
    min_value=30,
    max_value=365,
    value=120,
    step=15,
)

rerun = st.sidebar.button("Run Simulator")
if rerun:
    with st.spinner("Running simulator..."):
        run(horizon_days=horizon_days, capacity_multiplier=capacity_multiplier)

    st.success("Reports updated. Open the Risk Register tab to see results.")
    st.rerun()


st.title("✈️ Tech Ops Base Planning Dashboard")
st.caption("Forecast → Capacity Calendar → Maintenance Plan → Risk Register")

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader("Planning Inputs")

    horizon_days = st.slider("Planning Horizon (days)", 30, 365, 120, 10)
    capacity_multiplier = st.slider("Capacity Multiplier", 0.2, 1.5, 1.0, 0.1)

    st.info(
        "Tip: set Capacity Multiplier below ~0.7 to force constraints and populate the Risk Register."
    )

    run_btn = st.button("Run Forecast + Build Plan", type="primary")

if run_btn:
    paths = run(horizon_days=horizon_days, capacity_multiplier=capacity_multiplier, write_reports=True)
    st.success("Simulation complete. Reports refreshed.")

# Always try to display latest outputs if they exist
reports_dir = Path("reports")
plan_path = reports_dir / "maintenance_plan.csv"
cap_path = reports_dir / "capacity_calendar.csv"
risk_path = reports_dir / "risk_register.csv"
chart_path = reports_dir / "workload_vs_capacity.png"

with right:
    st.subheader("Outputs")

    tab1, tab2, tab3, tab4 = st.tabs(["Maintenance Plan", "Capacity Calendar", "Risk Register", "Workload Chart"])

    with tab1:
        if plan_path.exists():
            df = pd.read_csv(plan_path)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No maintenance_plan.csv yet. Click **Run Forecast + Build Plan**.")

    with tab2:
        if cap_path.exists():
            df = pd.read_csv(cap_path)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No capacity_calendar.csv yet.")

    with tab3:
        if risk_path.exists():
                try:
                    df = pd.read_csv(risk_path)
                except EmptyDataError:
                    df = pd.DataFrame()
                if df.empty:
                    st.info(
                        "Risk Register is empty — your plan fits capacity + windows. "
                        "Lower capacity to see risks."
                    )
                else:
                    st.dataframe(df, width="stretch")
        else:
            st.warning("No risk_register.csv yet.")

    with tab4:
        if chart_path.exists():
            st.image(str(chart_path), use_container_width=True)
        else:
            st.warning("No chart yet.")