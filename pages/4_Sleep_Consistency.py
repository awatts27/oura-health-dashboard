"""Sleep consistency analysis — bedtime/wake time, midpoint drift, social jet lag."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from data_processing import sleep_consistency_stats

st.title("Sleep Consistency")

sp = st.session_state.get("sleep_periods")
daily = st.session_state.get("daily")

if sp is None or sp.empty:
    st.info("No sleep period data available. Load data from the Overview page first.")
    st.stop()


def _fmt_hour(h: float) -> str:
    """Format a decimal hour (e.g. 23.5) as HH:MM."""
    h_int = int(h) % 24
    m_int = int((h - int(h)) * 60)
    return f"{h_int:02d}:{m_int:02d}"


# ── Bedtime and wake time over time ─────────────────────────────────────────

st.subheader("Bedtime & Wake Time Over Time")

has_bedtime = "bedtime_hour_adj" in sp.columns
has_wake = "waketime_hour" in sp.columns

if has_bedtime or has_wake:
    fig = go.Figure()

    if has_bedtime:
        fig.add_trace(go.Scatter(
            x=sp["day"], y=sp["bedtime_hour_adj"],
            mode="markers+lines",
            name="Bedtime",
            marker=dict(size=5, color="#7C3AED"),
            line=dict(width=1, color="#7C3AED"),
            hovertemplate="%{x|%b %d}<br>Bedtime: %{customdata}<extra></extra>",
            customdata=sp["bedtime_hour_adj"].apply(_fmt_hour),
        ))
        # Rolling average
        if len(sp) >= 7:
            sp_sorted = sp.sort_values("day")
            bt_ma = sp_sorted["bedtime_hour_adj"].rolling(7, min_periods=3).mean()
            fig.add_trace(go.Scatter(
                x=sp_sorted["day"], y=bt_ma,
                mode="lines",
                name="Bedtime 7d avg",
                line=dict(width=2, color="#7C3AED", dash="dash"),
            ))

    if has_wake:
        fig.add_trace(go.Scatter(
            x=sp["day"], y=sp["waketime_hour"],
            mode="markers+lines",
            name="Wake time",
            marker=dict(size=5, color="#06B6D4"),
            line=dict(width=1, color="#06B6D4"),
            hovertemplate="%{x|%b %d}<br>Wake: %{customdata}<extra></extra>",
            customdata=sp["waketime_hour"].apply(_fmt_hour),
        ))
        if len(sp) >= 7:
            sp_sorted = sp.sort_values("day")
            wt_ma = sp_sorted["waketime_hour"].rolling(7, min_periods=3).mean()
            fig.add_trace(go.Scatter(
                x=sp_sorted["day"], y=wt_ma,
                mode="lines",
                name="Wake 7d avg",
                line=dict(width=2, color="#06B6D4", dash="dash"),
            ))

    fig.update_layout(
        template="plotly_dark",
        height=400,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis_title="Hour of Day",
        xaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Bedtime/wake time data not available.")

# ── Sleep midpoint drift ────────────────────────────────────────────────────

st.subheader("Sleep Midpoint Drift")

if "sleep_midpoint" in sp.columns:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sp["day"], y=sp["sleep_midpoint"],
        mode="markers+lines",
        marker=dict(size=5, color="#F59E0B"),
        line=dict(width=1, color="#F59E0B"),
        name="Sleep Midpoint",
        hovertemplate="%{x|%b %d}<br>Midpoint: %{customdata}<extra></extra>",
        customdata=sp["sleep_midpoint"].apply(_fmt_hour),
    ))

    if len(sp) >= 7:
        sp_sorted = sp.sort_values("day")
        mp_ma = sp_sorted["sleep_midpoint"].rolling(7, min_periods=3).mean()
        fig.add_trace(go.Scatter(
            x=sp_sorted["day"], y=mp_ma,
            mode="lines",
            name="7-day avg",
            line=dict(width=2, color="#F59E0B", dash="dash"),
        ))

    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis_title="Hour of Day",
        xaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sleep midpoint data not available.")

# ── Social jet lag ──────────────────────────────────────────────────────────

st.subheader("Social Jet Lag")

if "day" in sp.columns:
    sp_with_weekend = sp.copy()
    sp_with_weekend["is_weekend"] = sp_with_weekend["day"].dt.dayofweek >= 5
    stats = sleep_consistency_stats(sp_with_weekend)

    if stats:
        cols = st.columns(4)

        if "social_jet_lag_hrs" in stats:
            sjl = stats["social_jet_lag_hrs"]
            severity = "Low" if sjl < 0.5 else ("Moderate" if sjl < 1.0 else "High")
            severity_color = "green" if sjl < 0.5 else ("orange" if sjl < 1.0 else "red")
            cols[0].metric("Social Jet Lag", f"{sjl:.1f} hrs")
            cols[0].markdown(
                f"<span style='color:{severity_color}'>{severity}</span>",
                unsafe_allow_html=True,
            )

        if "weekday_midpoint" in stats:
            cols[1].metric("Weekday Midpoint", _fmt_hour(stats["weekday_midpoint"]))

        if "weekend_midpoint" in stats:
            cols[2].metric("Weekend Midpoint", _fmt_hour(stats["weekend_midpoint"]))

        if "bedtime_std_hrs" in stats:
            cols[3].metric("Bedtime Variability", f"±{stats['bedtime_std_hrs']:.1f} hrs")

        # Weekday vs weekend distribution
        if "bedtime_hour_adj" in sp_with_weekend.columns:
            st.markdown("**Bedtime Distribution: Weekday vs Weekend**")
            fig = go.Figure()
            for is_wkend, label, color in [(False, "Weekday", "#7C3AED"), (True, "Weekend", "#06B6D4")]:
                subset = sp_with_weekend[sp_with_weekend["is_weekend"] == is_wkend]
                if not subset.empty:
                    fig.add_trace(go.Histogram(
                        x=subset["bedtime_hour_adj"],
                        name=label,
                        opacity=0.7,
                        marker_color=color,
                        nbinsx=20,
                    ))
            fig.update_layout(
                template="plotly_dark",
                height=300,
                barmode="overlay",
                margin=dict(l=20, r=20, t=10, b=20),
                xaxis_title="Bedtime (hour)",
                yaxis_title="Count",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough sleep period data to compute social jet lag.")
