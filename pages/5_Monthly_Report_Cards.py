"""Monthly and quarterly report cards with summary stats, streaks, and grades."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from data_processing import monthly_summary, compute_streaks, health_trend_grade

st.title("Monthly Report Cards")

daily = st.session_state.get("daily")
if daily is None or daily.empty:
    st.info("Load data from the main Overview page first.")
    st.stop()

KEY_METRICS = ["sleep_score", "readiness_score", "activity_score", "steps", "resting_hr"]
available_metrics = [m for m in KEY_METRICS if m in daily.columns]

FRIENDLY = {
    "sleep_score": "Sleep Score",
    "readiness_score": "Readiness Score",
    "activity_score": "Activity Score",
    "steps": "Steps",
    "resting_hr": "Resting HR",
}

# ── Overall health grade ────────────────────────────────────────────────────

grade = health_trend_grade(daily)
grade_colors = {"Improving": "#10B981", "Declining": "#EF4444", "Stable": "#F59E0B", "N/A": "#6B7280"}
color = grade_colors.get(grade, "#6B7280")

st.markdown(
    f"### Health Trend Grade: "
    f"<span style='color:{color};font-size:1.4em'>{grade}</span>",
    unsafe_allow_html=True,
)

# ── Streaks ─────────────────────────────────────────────────────────────────

st.subheader("Streaks")
streak_cols = st.columns(len(available_metrics))
thresholds = {"sleep_score": 70, "readiness_score": 70, "activity_score": 70, "steps": 7000, "resting_hr": 999}

for col_w, metric in zip(streak_cols, available_metrics):
    threshold = thresholds.get(metric, 70)
    streaks = compute_streaks(daily[metric], threshold)
    label = FRIENDLY.get(metric, metric)
    # For resting_hr, a streak above 999 is meaningless — skip
    if metric == "resting_hr":
        col_w.metric(f"{label} (lowest)", f"{daily[metric].min():.0f}")
    else:
        col_w.metric(
            f"{label} ≥ {threshold}",
            f"{streaks['current_streak']}d current",
            f"Longest: {streaks['longest_streak']}d",
        )

# ── Monthly summary table ──────────────────────────────────────────────────

st.markdown("---")
st.subheader("Monthly Summary")

summary = monthly_summary(daily, available_metrics)

if summary.empty:
    st.info("Not enough data for monthly breakdown.")
    st.stop()

# Display as formatted table
months = summary["month"].tolist()
selected_month = st.selectbox("Select month", months, index=len(months) - 1)

month_data = summary[summary["month"] == selected_month].iloc[0]
prev_month_idx = months.index(selected_month) - 1

card_cols = st.columns(len(available_metrics))
for col_w, metric in zip(card_cols, available_metrics):
    label = FRIENDLY.get(metric, metric)
    mean_val = month_data.get(f"{metric}_mean", np.nan)
    min_val = month_data.get(f"{metric}_min", np.nan)
    max_val = month_data.get(f"{metric}_max", np.nan)

    delta_str = None
    if prev_month_idx >= 0:
        prev = summary.iloc[prev_month_idx]
        prev_mean = prev.get(f"{metric}_mean", np.nan)
        if pd.notna(mean_val) and pd.notna(prev_mean):
            diff = mean_val - prev_mean
            delta_str = f"{diff:+.1f} vs prev month"

    if pd.notna(mean_val):
        col_w.metric(label, f"{mean_val:.1f}", delta=delta_str)
        col_w.caption(f"Range: {min_val:.0f} – {max_val:.0f}")
    else:
        col_w.metric(label, "—")

# ── Month-over-month trend chart ────────────────────────────────────────────

st.markdown("---")
st.subheader("Month-over-Month Trends")

metric_to_chart = st.selectbox(
    "Metric",
    available_metrics,
    format_func=lambda m: FRIENDLY.get(m, m),
)

mean_col = f"{metric_to_chart}_mean"
if mean_col in summary.columns:
    values = summary[mean_col]
    colors = []
    for i, val in enumerate(values):
        if i == 0:
            colors.append("#7C3AED")
        elif val > values.iloc[i - 1]:
            colors.append("#10B981")  # improved
        elif val < values.iloc[i - 1]:
            colors.append("#EF4444")  # declined
        else:
            colors.append("#F59E0B")  # stable

    fig = go.Figure(data=go.Bar(
        x=summary["month"],
        y=summary[mean_col],
        marker_color=colors,
        text=summary[mean_col].round(1),
        textposition="outside",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis_title=FRIENDLY.get(metric_to_chart, metric_to_chart),
        xaxis_title="Month",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Full monthly data table ─────────────────────────────────────────────────

with st.expander("Full monthly data"):
    display = summary.copy()
    # Rename columns for readability
    rename_map = {"month": "Month"}
    for m in available_metrics:
        label = FRIENDLY.get(m, m)
        rename_map[f"{m}_mean"] = f"{label} (avg)"
        rename_map[f"{m}_min"] = f"{label} (min)"
        rename_map[f"{m}_max"] = f"{label} (max)"
        rename_map[f"{m}_std"] = f"{label} (std)"
    display = display.rename(columns=rename_map)
    st.dataframe(display.round(1), use_container_width=True, hide_index=True)
