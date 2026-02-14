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
    "HRV": "average_hrv",
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

# ── Heatmap (per-metric z-score normalization) ──────────────────────────────

st.subheader("Heatmap — Average Metrics by Day")
st.caption("Colors are normalized per row (metric) to highlight each metric's own weekly pattern. Greener = better for that metric.")

# Drop metrics that are entirely NaN (e.g. Resting HR if no HR data)
valid_metrics = {k: v for k, v in available.items()
                 if v in dow.columns and dow[v].notna().any()}
valid_cols = list(valid_metrics.values())
valid_labels = list(valid_metrics.keys())

if valid_cols:
    heatmap_data = dow.set_index("day_of_week")[valid_cols].T

    # Normalize each row (metric) to 0-1 range so different scales are comparable
    raw_values = heatmap_data.values
    row_min = raw_values.min(axis=1, keepdims=True)
    row_max = raw_values.max(axis=1, keepdims=True)
    row_range = row_max - row_min
    row_range[row_range == 0] = 1  # avoid division by zero
    normalized = (raw_values - row_min) / row_range

    # For resting HR, invert (lower is better)
    for i, col in enumerate(valid_cols):
        if col == "resting_hr":
            normalized[i] = 1.0 - normalized[i]

    # Subtle green-gray palette instead of screaming red-yellow-green
    subtle_scale = [
        [0.0, "#3b3b4f"],    # muted dark (worst)
        [0.35, "#4a5568"],   # gray
        [0.5, "#718096"],    # neutral gray
        [0.7, "#68d391"],    # soft green
        [1.0, "#38a169"],    # green (best)
    ]

    fig = go.Figure(data=go.Heatmap(
        z=normalized,
        x=heatmap_data.columns.tolist(),
        y=valid_labels,
        colorscale=subtle_scale,
        text=heatmap_data.values.round(0).astype(int),
        texttemplate="%{text}",
        textfont=dict(size=12, color="white"),
        showscale=False,
    ))
    fig.update_layout(
        template="plotly_dark",
        height=50 + 60 * len(valid_labels),
        margin=dict(l=20, r=20, t=10, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No metrics with enough data for the heatmap.")

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
        text=dow[col].round(0).astype(int),
        textposition="outside",
        textfont=dict(size=11),
    ))
    y_max = dow[col].max()
    y_min = dow[col].min()
    pad = (y_max - y_min) * 0.15 if y_max != y_min else y_max * 0.1
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis_title=label,
        yaxis_range=[max(0, y_min - pad), y_max + pad],
        xaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Weekend vs Weekday comparison ────────────────────────────────────────────

st.markdown("---")
st.subheader("Weekend vs Weekday")

if "is_weekend" in daily.columns:
    wkday_means = daily.loc[~daily["is_weekend"], metric_cols].mean()
    wkend_means = daily.loc[daily["is_weekend"], metric_cols].mean()

    # Plain-language callouts for meaningful differences
    callouts = []
    for label, col in available.items():
        if col not in wkday_means.index:
            continue
        diff = wkend_means[col] - wkday_means[col]
        if col == "resting_hr":
            if abs(diff) > 1:
                better = "weekdays" if diff > 0 else "weekends"
                callouts.append(f"Resting HR is **{abs(diff):.0f} bpm lower** on {better}")
        elif col == "average_hrv":
            if abs(diff) > 2:
                higher = "weekends" if diff > 0 else "weekdays"
                callouts.append(f"HRV is **{abs(diff):.0f} ms higher** on {higher}")
        elif col == "steps":
            if abs(diff) > 500:
                more = "weekends" if diff > 0 else "weekdays"
                callouts.append(f"You walk **{abs(diff):.0f} more steps** on {more}")
        else:
            if abs(diff) > 2:
                better = "weekends" if diff > 0 else "weekdays"
                callouts.append(f"{label} is **{abs(diff):.0f} points higher** on {better}")

    if callouts:
        for c in callouts:
            st.markdown(f"- {c}")
    else:
        st.info("No meaningful differences between weekdays and weekends.")

    # Still show the table, but collapsed
    with st.expander("Full comparison table"):
        comparison = pd.DataFrame({
            "Weekday": wkday_means,
            "Weekend": wkend_means,
        })
        comparison.index = [k for k, v in available.items() if v in comparison.index.tolist()] or comparison.index
        comparison["Difference"] = comparison["Weekend"] - comparison["Weekday"]
        comparison["Diff %"] = (comparison["Difference"] / comparison["Weekday"] * 100).round(1)
        st.dataframe(comparison.round(0), use_container_width=True)
