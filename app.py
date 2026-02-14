"""Oura Health Analytics Dashboard — main entry point."""

import pandas as pd
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
    daily_hrv,
    enrich_sleep_periods,
    health_trend_grade,
    compute_trend,
    generate_key_findings,
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

hrv_df = daily_hrv(data)
if not hrv_df.empty and not daily.empty:
    daily = daily.merge(hrv_df, on="day", how="left")

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

# KPI row — compare latest value against 7-day rolling average
cols = st.columns(6)


def _latest(col: str):
    if col in daily.columns:
        vals = daily[col].dropna()
        return vals.iloc[-1] if len(vals) else None
    return None


def _recent_avg(col: str, window: int = 7):
    """Average of the prior `window` days (excluding the latest day)."""
    if col in daily.columns:
        vals = daily[col].dropna()
        if len(vals) > window:
            return vals.iloc[-(window + 1):-1].mean()
        return vals.mean()
    return None


def _trend_icon(col: str) -> str:
    if col not in daily.columns:
        return ""
    t = compute_trend(daily[col])
    icons = {"improving": " ↑", "declining": " ↓", "stable": " →"}
    return icons.get(t, "")


metrics = [
    ("Sleep Score", "sleep_score", "😴"),
    ("Readiness", "readiness_score", "⚡"),
    ("HRV (ms)", "average_hrv", "💓"),
    ("Activity", "activity_score", "🏃"),
    ("Resting HR", "resting_hr", "❤️"),
    ("Steps", "steps", "👟"),
]

# Metrics where a LOWER value is better (positive delta = bad)
LOWER_IS_BETTER = {"resting_hr"}

for col_widget, (label, key, emoji) in zip(cols, metrics):
    latest = _latest(key)
    avg = _recent_avg(key)
    if latest is not None and avg is not None:
        delta = latest - avg
        col_widget.metric(
            label=f"{emoji} {label}{_trend_icon(key)}",
            value=f"{latest:.0f}",
            delta=f"{delta:+.1f} vs 7d avg",
            delta_color="inverse" if key in LOWER_IS_BETTER else "normal",
        )
    else:
        col_widget.metric(label=f"{emoji} {label}", value="—")

# Show which date the latest values are from
latest_day = daily["day"].dropna().iloc[-1] if not daily["day"].dropna().empty else None
if latest_day is not None:
    st.caption(f"Latest data: **{latest_day.strftime('%A, %b %d %Y')}**")

# ── Key findings ────────────────────────────────────────────────────────────

findings = generate_key_findings(daily, sp)
if findings:
    st.markdown("### Key Findings")
    with st.container(border=True):
        for f in findings:
            st.markdown(f"- {f}")

st.markdown("---")

# ── Last 7 days with conditional highlighting ───────────────────────────────

st.subheader("Last 7 Days")
recent = daily.tail(7)
display_cols = [c for c in ["day", "sleep_score", "readiness_score", "average_hrv", "activity_score", "steps", "resting_hr"] if c in recent.columns]

COLUMN_LABELS = {
    "day": "Day",
    "sleep_score": "Sleep",
    "readiness_score": "Readiness",
    "average_hrv": "HRV",
    "activity_score": "Activity",
    "steps": "Steps",
    "resting_hr": "Resting HR",
}

if display_cols:
    show = recent[display_cols].copy()
    if "day" in show.columns:
        show["day"] = show["day"].dt.strftime("%a %b %d")

    # Round numeric columns to remove excessive decimals
    num_cols = show.select_dtypes(include="number").columns
    show[num_cols] = show[num_cols].round(0).astype("Int64")

    # Rename to friendly labels
    show = show.rename(columns=COLUMN_LABELS)

    # Highlight cells based on value quality
    SCORE_LABELS = [COLUMN_LABELS[c] for c in ["sleep_score", "readiness_score", "activity_score"] if c in display_cols]

    def _color_scores(val):
        """Green for good scores, red for poor, neutral for average."""
        if not isinstance(val, (int, float)) or pd.isna(val):
            return ""
        if val >= 85:
            return "color: #10B981"
        elif val >= 70:
            return ""
        elif val >= 60:
            return "color: #F59E0B"
        else:
            return "color: #EF4444"

    def _color_hr(val):
        """Lower resting HR is better."""
        if not isinstance(val, (int, float)) or pd.isna(val):
            return ""
        if val <= 55:
            return "color: #10B981"
        elif val >= 70:
            return "color: #EF4444"
        return ""

    def _color_hrv(val):
        """Higher HRV is better."""
        if not isinstance(val, (int, float)) or pd.isna(val):
            return ""
        if val >= 50:
            return "color: #10B981"
        elif val <= 20:
            return "color: #EF4444"
        return ""

    styled = show.style
    if SCORE_LABELS:
        styled = styled.map(_color_scores, subset=SCORE_LABELS)
    if "HRV" in show.columns:
        styled = styled.map(_color_hrv, subset=["HRV"])
    if "Resting HR" in show.columns:
        styled = styled.map(_color_hr, subset=["Resting HR"])

    st.dataframe(styled, use_container_width=True, hide_index=True)
