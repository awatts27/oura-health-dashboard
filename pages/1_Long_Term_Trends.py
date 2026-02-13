"""Long-term trend analysis with rolling averages and trend indicators."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_processing import add_rolling_averages, compute_trend, compute_trend_detail

st.title("Long-term Trends")

daily = st.session_state.get("daily")
if daily is None or daily.empty:
    st.info("Load data from the main Overview page first.")
    st.stop()

# Metrics to trend
METRIC_OPTIONS = {
    "Sleep Score": "sleep_score",
    "Readiness Score": "readiness_score",
    "Activity Score": "activity_score",
    "Resting HR": "resting_hr",
    "Steps": "steps",
}

available = {k: v for k, v in METRIC_OPTIONS.items() if v in daily.columns}

if not available:
    st.warning("No trendable metrics found in data.")
    st.stop()

selected_labels = st.multiselect(
    "Metrics to display",
    list(available.keys()),
    default=list(available.keys())[:4],
)

windows = st.multiselect(
    "Rolling average windows (days)",
    [7, 14, 30, 60, 90],
    default=[30, 90],
)

selected_cols = [available[l] for l in selected_labels]
df = add_rolling_averages(daily, selected_cols, windows)

for label in selected_labels:
    col = available[label]
    if col not in df.columns:
        continue

    detail = compute_trend_detail(df[col], window=30)
    trend = detail["direction"]
    trend_icons = {"improving": "↑ Improving", "declining": "↓ Declining", "stable": "→ Stable"}
    trend_text = trend_icons.get(trend, trend)
    trend_colors = {"improving": "green", "declining": "red", "stable": "orange"}
    color = trend_colors.get(trend, "gray")

    st.markdown(
        f"### {label} "
        f"<span style='font-size:0.8em;color:{color}'>{trend_text}</span>",
        unsafe_allow_html=True,
    )

    # Plain-language description of the trend
    if trend in ("improving", "declining"):
        verb = "up" if detail["change"] > 0 else "down"
        st.caption(
            f"~{abs(detail['change']):.0f} points {verb} over the last "
            f"{detail['days']} days ({detail['slope_per_day']:+.1f}/day)"
        )
    elif trend == "stable":
        st.caption(f"Holding steady over the last {detail['days']} days")

    fig = go.Figure()

    # Raw data as light scatter
    fig.add_trace(go.Scatter(
        x=df["day"], y=df[col],
        mode="markers",
        marker=dict(size=3, color="rgba(124, 58, 237, 0.3)"),
        name="Daily",
    ))

    # Rolling averages
    colors = ["#7C3AED", "#06B6D4", "#F59E0B", "#EF4444", "#10B981"]
    for i, w in enumerate(sorted(windows)):
        ma_col = f"{col}_ma{w}"
        if ma_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["day"], y=df[ma_col],
                mode="lines",
                line=dict(width=2, color=colors[i % len(colors)]),
                name=f"{w}-day MA",
            ))

    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="",
        yaxis_title=label,
    )
    st.plotly_chart(fig, use_container_width=True)
