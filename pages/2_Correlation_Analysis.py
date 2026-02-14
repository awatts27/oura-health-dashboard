"""Interactive correlation analysis between health metrics."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from data_processing import compute_correlation, interpret_r

st.title("Correlation Analysis")

daily = st.session_state.get("daily")
if daily is None or daily.empty:
    st.info("Load data from the main Overview page first.")
    st.stop()

# All numeric columns available for correlation
numeric_cols = daily.select_dtypes(include="number").columns.tolist()
exclude = {"week_number"}
numeric_cols = [c for c in numeric_cols if c not in exclude]

FRIENDLY_NAMES = {
    "sleep_score": "Sleep Score",
    "readiness_score": "Readiness Score",
    "average_hrv": "HRV",
    "activity_score": "Activity Score",
    "steps": "Steps",
    "resting_hr": "Resting HR",
    "avg_hr": "Avg HR",
    "total_calories": "Total Calories",
    "active_calories": "Active Calories",
    "high_activity_time": "High Activity Time",
    "medium_activity_time": "Medium Activity Time",
    "sedentary_time": "Sedentary Time",
}


def friendly(col: str) -> str:
    return FRIENDLY_NAMES.get(col, col.replace("_", " ").title())


# ── Pre-built correlation pairs ──────────────────────────────────────────────

st.subheader("Pre-built Correlation Pairs")

PREBUILT = [
    ("sleep_score", "readiness_score", "Sleep Score vs Readiness Score"),
    ("average_hrv", "readiness_score", "HRV vs Readiness Score"),
    ("average_hrv", "sleep_score", "HRV vs Sleep Score"),
    ("sleep_score", "resting_hr", "Sleep Score vs Resting HR"),
    ("activity_score", "sleep_score", "Activity Score vs Sleep Score"),
]

pair_cols = st.columns(2)
for i, (col_a, col_b, title) in enumerate(PREBUILT):
    if col_a not in daily.columns or col_b not in daily.columns:
        continue

    r, p, n = compute_correlation(daily, col_a, col_b)

    with pair_cols[i % 2]:
        st.markdown(f"**{title}**")
        if np.isnan(r):
            st.write("Not enough data")
            continue

        interpretation = interpret_r(r)
        sig = "statistically significant" if p < 0.05 else "not statistically significant"
        st.markdown(f"**{interpretation.capitalize()}** ({sig}, n={n})")
        st.caption(f"R = {r:.2f} · R² = {r**2:.2f} · p = {p:.3f}")

        fig = px.scatter(
            daily, x=col_a, y=col_b,
            trendline="ols",
            labels={col_a: friendly(col_a), col_b: friendly(col_b)},
            template="plotly_dark",
            opacity=0.6,
        )
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=10, b=20),
        )
        fig.update_traces(marker=dict(color="#7C3AED", size=5))
        st.plotly_chart(fig, use_container_width=True)

# ── Custom correlation explorer ──────────────────────────────────────────────

st.markdown("---")
st.subheader("Custom Correlation Explorer")

c1, c2 = st.columns(2)
with c1:
    x_col = st.selectbox("X axis", numeric_cols, index=0, format_func=friendly)
with c2:
    default_y = min(1, len(numeric_cols) - 1)
    y_col = st.selectbox("Y axis", numeric_cols, index=default_y, format_func=friendly)

if x_col and y_col and x_col != y_col:
    r, p, n = compute_correlation(daily, x_col, y_col)

    if not np.isnan(r):
        interpretation = interpret_r(r)
        sig = "statistically significant" if p < 0.05 else "not statistically significant"
        st.markdown(
            f"**{interpretation.capitalize()}** — {sig} (n={n})"
        )
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("R", f"{r:.2f}")
        mc2.metric("R²", f"{r**2:.2f}")
        mc3.metric("n", str(n))
        mc4.metric("p-value", f"{p:.3f}")

        fig = px.scatter(
            daily, x=x_col, y=y_col,
            trendline="ols",
            labels={x_col: friendly(x_col), y_col: friendly(y_col)},
            template="plotly_dark",
            opacity=0.6,
        )
        fig.update_layout(
            height=450,
            margin=dict(l=20, r=20, t=10, b=20),
        )
        fig.update_traces(marker=dict(color="#7C3AED", size=6))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"Not enough overlapping data points for {friendly(x_col)} vs {friendly(y_col)}.")
elif x_col == y_col:
    st.info("Select two different metrics to compare.")

# ── Correlation matrix ───────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Correlation Matrix")

key_metrics = [c for c in ["sleep_score", "readiness_score", "average_hrv",
                            "activity_score", "steps", "resting_hr", "avg_hr",
                            "total_calories", "active_calories",
                            "sedentary_time"] if c in daily.columns]

if len(key_metrics) >= 2:
    corr = daily[key_metrics].corr()
    labels = [friendly(c) for c in key_metrics]

    # Use a muted blue-gray-orange palette instead of intense red-blue
    corr_scale = [
        [0.0, "#4a6fa5"],   # muted blue (negative)
        [0.5, "#2d3748"],   # dark gray (zero)
        [1.0, "#c97b3d"],   # muted amber (positive)
    ]
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=labels,
        y=labels,
        colorscale=corr_scale,
        zmid=0,
        text=corr.values.round(2),
        texttemplate="%{text}",
        textfont=dict(size=11, color="white"),
    ))
    fig.update_layout(
        template="plotly_dark",
        height=500,
        margin=dict(l=20, r=20, t=10, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Need at least 2 key metrics to build a correlation matrix.")
