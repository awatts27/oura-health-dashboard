"""Oura Health Analytics Dashboard — main entry point."""

import streamlit as st

st.set_page_config(
    page_title="Oura Health Dashboard",
    page_icon="💤",
    layout="wide",
    initial_sidebar_state="expanded",
)

from oura_api import fetch_all_data
from data_processing import (
    build_daily_df,
    daily_hr_stats,
    enrich_sleep_periods,
    health_trend_grade,
    compute_trend,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("Oura Health Dashboard")
days = st.sidebar.selectbox("Date range", [90, 180, 365], format_func=lambda d: f"Last {d} days")
if st.sidebar.button("Clear cache & reload"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Navigate using the pages in the sidebar.\n\n"
    "Data is cached for 1 hour to avoid excessive API calls."
)

# ── Load data ────────────────────────────────────────────────────────────────

data = fetch_all_data(days)
daily = build_daily_df(data)
hr_stats = daily_hr_stats(data)

if not hr_stats.empty and not daily.empty:
    daily = daily.merge(hr_stats, on="day", how="left")

sp = enrich_sleep_periods(data)

# Store in session state so pages can access without re-fetching
st.session_state["oura_data"] = data
st.session_state["daily"] = daily
st.session_state["sleep_periods"] = sp
st.session_state["days"] = days

# ── Overview page ────────────────────────────────────────────────────────────

st.title("Overview")

if daily.empty:
    st.warning("No data returned from Oura. Verify your token and that you have data for the selected range.")
    st.stop()

# KPI row
cols = st.columns(5)

def _latest(col: str):
    if col in daily.columns:
        vals = daily[col].dropna()
        return vals.iloc[-1] if len(vals) else None
    return None

def _avg(col: str):
    if col in daily.columns:
        return daily[col].mean()
    return None

def _trend_icon(col: str) -> str:
    if col not in daily.columns:
        return ""
    t = compute_trend(daily[col])
    icons = {"improving": " ↑", "declining": " ↓", "stable": " →"}
    return icons.get(t, "")

metrics = [
    ("Sleep Score", "sleep_score"),
    ("Readiness Score", "readiness_score"),
    ("Activity Score", "activity_score"),
    ("Resting HR", "resting_hr"),
    ("Steps", "steps"),
]

for col_widget, (label, key) in zip(cols, metrics):
    latest = _latest(key)
    avg = _avg(key)
    if latest is not None and avg is not None:
        delta = latest - avg
        col_widget.metric(
            label=f"{label}{_trend_icon(key)}",
            value=f"{latest:.0f}",
            delta=f"{delta:+.1f} vs avg",
        )
    else:
        col_widget.metric(label=label, value="—")

# Health trend grade
grade = health_trend_grade(daily)
grade_colors = {"Improving": "green", "Declining": "red", "Stable": "orange"}
grade_color = grade_colors.get(grade, "gray")
st.markdown(
    f"### Overall Health Trend: "
    f"<span style='color:{grade_color};font-weight:bold'>{grade}</span>",
    unsafe_allow_html=True,
)

st.markdown("---")

# Quick summary table — last 7 days
st.subheader("Last 7 Days")
recent = daily.tail(7)
display_cols = [c for c in ["day", "sleep_score", "readiness_score", "activity_score", "steps", "resting_hr"] if c in recent.columns]
if display_cols:
    show = recent[display_cols].copy()
    if "day" in show.columns:
        show["day"] = show["day"].dt.strftime("%a %b %d")
    st.dataframe(show, use_container_width=True, hide_index=True)
