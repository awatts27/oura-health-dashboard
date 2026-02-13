"""Day-of-week patterns — heatmap and grouped bar charts."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from data_processing import day_of_week_stats

st.title("Day-of-Week Patterns")

daily = st.session_state.get("daily")
if daily is None or daily.empty:
    st.info("Load data from the main Overview page first.")
    st.stop()

METRICS = {
    "Sleep Score": "sleep_score",
    "Readiness Score": "readiness_score",
    "Activity Score": "activity_score",
    "Resting HR": "resting_hr",
    "Steps": "steps",
}

available = {k: v for k, v in METRICS.items() if v in daily.columns}
if not available:
    st.warning("No metrics available for day-of-week analysis.")
    st.stop()

metric_cols = list(available.values())
dow = day_of_week_stats(daily, metric_cols)

if dow.empty:
    st.warning("Not enough data for day-of-week analysis.")
    st.stop()

# ── Heatmap ──────────────────────────────────────────────────────────────────

st.subheader("Heatmap — Average Metrics by Day")

heatmap_data = dow.set_index("day_of_week")[metric_cols].T
labels = [k for k, v in available.items()]

fig = go.Figure(data=go.Heatmap(
    z=heatmap_data.values,
    x=heatmap_data.columns.tolist(),
    y=labels,
    colorscale="Viridis",
    text=heatmap_data.values.round(1),
    texttemplate="%{text}",
    textfont=dict(size=12),
))
fig.update_layout(
    template="plotly_dark",
    height=50 + 60 * len(labels),
    margin=dict(l=20, r=20, t=10, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# ── Grouped bar charts per metric ────────────────────────────────────────────

st.subheader("Detailed Breakdown")

for label, col in available.items():
    if col not in dow.columns:
        continue

    values = dow[col]
    best_day = dow.loc[values.idxmax(), "day_of_week"]
    worst_day = dow.loc[values.idxmin(), "day_of_week"]

    # For resting HR, lower is better
    if col == "resting_hr":
        best_day, worst_day = worst_day, best_day

    st.markdown(
        f"**{label}** — Best: **{best_day}** / Worst: **{worst_day}**"
    )

    colors = ["#7C3AED"] * len(dow)
    best_idx = dow.index[dow["day_of_week"] == best_day].tolist()
    worst_idx = dow.index[dow["day_of_week"] == worst_day].tolist()
    if best_idx:
        colors[best_idx[0]] = "#10B981"
    if worst_idx:
        colors[worst_idx[0]] = "#EF4444"

    fig = go.Figure(data=go.Bar(
        x=dow["day_of_week"],
        y=dow[col],
        marker_color=colors,
        text=dow[col].round(1),
        textposition="outside",
    ))
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis_title=label,
        xaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Weekend vs Weekday comparison ────────────────────────────────────────────

st.markdown("---")
st.subheader("Weekend vs Weekday")

if "is_weekend" in daily.columns:
    comparison = daily.groupby("is_weekend")[metric_cols].mean().T
    comparison.columns = ["Weekday", "Weekend"]
    comparison.index = [k for k, v in available.items() if v in comparison.index.tolist()] or comparison.index
    comparison["Difference"] = comparison["Weekend"] - comparison["Weekday"]
    comparison["Diff %"] = (comparison["Difference"] / comparison["Weekday"] * 100).round(1)
    st.dataframe(comparison.round(1), use_container_width=True)
