"""Personal tagging — tag days and see how they affect your metrics."""

import json
import os
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

st.title("Personal Tags")

daily = st.session_state.get("daily")
if daily is None or daily.empty:
    st.info("Load data from the main Overview page first.")
    st.stop()

TAGS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "tags.json")

FRIENDLY = {
    "sleep_score": "Sleep Score",
    "readiness_score": "Readiness Score",
    "activity_score": "Activity Score",
    "steps": "Steps",
    "resting_hr": "Resting HR",
}

PRESET_TAGS = ["alcohol", "heavy workout", "travel", "stress", "sick", "poor diet", "great day", "meditation"]


def _load_tags() -> dict[str, list[str]]:
    """Load tags from JSON file. Keys are ISO date strings, values are tag lists."""
    if os.path.exists(TAGS_FILE):
        with open(TAGS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_tags(tags: dict[str, list[str]]):
    os.makedirs(os.path.dirname(TAGS_FILE), exist_ok=True)
    with open(TAGS_FILE, "w") as f:
        json.dump(tags, f, indent=2)


tags = _load_tags()

# ── Add / edit tags ─────────────────────────────────────────────────────────

st.subheader("Tag a Day")

c1, c2 = st.columns([1, 2])
with c1:
    min_day = daily["day"].min().date() if "day" in daily.columns else None
    max_day = daily["day"].max().date() if "day" in daily.columns else None
    tag_date = st.date_input("Date", value=max_day, min_value=min_day, max_value=max_day)

with c2:
    date_key = tag_date.isoformat() if tag_date else None
    existing = tags.get(date_key, [])

    selected_tags = st.multiselect(
        "Tags",
        options=PRESET_TAGS,
        default=[t for t in existing if t in PRESET_TAGS],
        key="tag_select",
    )
    custom_tag = st.text_input("Custom tag (optional)")

if st.button("Save tags"):
    if date_key:
        all_tags = list(selected_tags)
        if custom_tag.strip():
            all_tags.append(custom_tag.strip())
        if all_tags:
            tags[date_key] = all_tags
        elif date_key in tags:
            del tags[date_key]
        _save_tags(tags)
        st.success(f"Tags saved for {date_key}")
        st.rerun()

# ── Show tagged days ────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Tagged Days")

if not tags:
    st.info("No days tagged yet. Use the form above to start tagging days.")
    st.stop()

# Build a DataFrame of tags
tag_records = []
for date_str, tag_list in tags.items():
    for tag in tag_list:
        tag_records.append({"day": pd.Timestamp(date_str), "tag": tag})

tags_df = pd.DataFrame(tag_records)

if tags_df.empty:
    st.info("No tags recorded.")
    st.stop()

# Show summary
tag_counts = tags_df["tag"].value_counts()
st.dataframe(
    tag_counts.rename("Count").to_frame(),
    use_container_width=True,
)

# ── Impact analysis ─────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Tag Impact Analysis")

available_tags = sorted(tags_df["tag"].unique())
selected_tag = st.selectbox("Analyze tag", available_tags)

available_metrics = [m for m in FRIENDLY if m in daily.columns]

if selected_tag:
    tagged_dates = set(tags_df[tags_df["tag"] == selected_tag]["day"])
    daily_copy = daily.copy()
    daily_copy["tagged"] = daily_copy["day"].isin(tagged_dates)

    tagged_days = daily_copy[daily_copy["tagged"]]
    baseline_days = daily_copy[~daily_copy["tagged"]]

    n_tagged = len(tagged_days)
    n_baseline = len(baseline_days)
    st.markdown(f"**{selected_tag}**: {n_tagged} tagged days vs {n_baseline} baseline days")

    if n_tagged < 2:
        st.warning("Need at least 2 tagged days for meaningful comparison.")
    else:
        # Sample size warning
        if n_tagged < 10:
            st.caption(
                f"Based on only **{n_tagged} tagged days** — results are suggestive, "
                f"not conclusive. Tag more days for reliable insights."
            )

        # Comparison table
        comparison = []
        for metric in available_metrics:
            tagged_mean = tagged_days[metric].mean()
            baseline_mean = baseline_days[metric].mean()
            if pd.notna(tagged_mean) and pd.notna(baseline_mean):
                diff = tagged_mean - baseline_mean
                pct = (diff / baseline_mean * 100) if baseline_mean != 0 else 0
                comparison.append({
                    "Metric": FRIENDLY.get(metric, metric),
                    "metric_key": metric,
                    f"Tagged ({selected_tag})": round(tagged_mean, 1),
                    "Baseline": round(baseline_mean, 1),
                    "Difference": round(diff, 1),
                    "Diff %": round(pct, 1),
                })

        if comparison:
            comp_df = pd.DataFrame(comparison)
            display_df = comp_df.drop(columns=["metric_key"])
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Per-metric % difference chart (fixes the mixed-scale problem)
            st.markdown("**Impact as % difference from baseline**")
            fig = go.Figure()
            colors = []
            for _, row in comp_df.iterrows():
                pct = row["Diff %"]
                mk = row["metric_key"]
                # For resting HR, positive diff % is bad
                if mk == "resting_hr":
                    colors.append("#EF4444" if pct > 0 else "#10B981")
                else:
                    colors.append("#10B981" if pct > 0 else "#EF4444")

            fig.add_trace(go.Bar(
                x=comp_df["Metric"],
                y=comp_df["Diff %"],
                marker_color=colors,
                text=[f"{v:+.1f}%" for v in comp_df["Diff %"]],
                textposition="outside",
            ))
            fig.update_layout(
                template="plotly_dark",
                height=350,
                margin=dict(l=20, r=20, t=10, b=20),
                yaxis_title="% difference from baseline",
                xaxis_title="",
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            st.plotly_chart(fig, use_container_width=True)

    # ── Next-day impact (promoted with visualization) ───────────────────────

    st.markdown("---")
    st.subheader("Next-Day Effect")
    st.markdown(f"How do your metrics look the day **after** a *{selected_tag}* day?")

    next_day_comparison = []
    for metric in available_metrics:
        next_day_dates = {d + pd.Timedelta(days=1) for d in tagged_dates}
        next_day_data = daily_copy[daily_copy["day"].isin(next_day_dates) & ~daily_copy["tagged"]]
        if len(next_day_data) >= 2:
            nd_mean = next_day_data[metric].mean()
            bl_mean = baseline_days[metric].mean()
            if pd.notna(nd_mean) and pd.notna(bl_mean):
                diff = nd_mean - bl_mean
                pct = (diff / bl_mean * 100) if bl_mean != 0 else 0
                next_day_comparison.append({
                    "Metric": FRIENDLY.get(metric, metric),
                    "metric_key": metric,
                    "Day After": round(nd_mean, 1),
                    "Baseline": round(bl_mean, 1),
                    "Difference": round(diff, 1),
                    "Diff %": round(pct, 1),
                })

    if next_day_comparison:
        nd_df = pd.DataFrame(next_day_comparison)
        st.dataframe(nd_df.drop(columns=["metric_key"]), use_container_width=True, hide_index=True)

        # Visualize next-day effect
        nd_colors = []
        for _, row in nd_df.iterrows():
            pct = row["Diff %"]
            mk = row["metric_key"]
            if mk == "resting_hr":
                nd_colors.append("#EF4444" if pct > 0 else "#10B981")
            else:
                nd_colors.append("#10B981" if pct > 0 else "#EF4444")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=nd_df["Metric"],
            y=nd_df["Diff %"],
            marker_color=nd_colors,
            text=[f"{v:+.1f}%" for v in nd_df["Diff %"]],
            textposition="outside",
        ))
        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin=dict(l=20, r=20, t=10, b=20),
            yaxis_title="% difference from baseline",
            xaxis_title="",
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough next-day data for analysis.")
