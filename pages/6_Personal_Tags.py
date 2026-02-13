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
                    f"Tagged ({selected_tag})": round(tagged_mean, 1),
                    "Baseline": round(baseline_mean, 1),
                    "Difference": round(diff, 1),
                    "Diff %": round(pct, 1),
                })

        if comparison:
            comp_df = pd.DataFrame(comparison)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)

            # Visual comparison
            fig = go.Figure()
            metric_labels = comp_df["Metric"].tolist()
            fig.add_trace(go.Bar(
                x=metric_labels,
                y=comp_df["Baseline"],
                name="Baseline",
                marker_color="#6B7280",
            ))
            fig.add_trace(go.Bar(
                x=metric_labels,
                y=comp_df[f"Tagged ({selected_tag})"],
                name=f"Tagged ({selected_tag})",
                marker_color="#7C3AED",
            ))
            fig.update_layout(
                template="plotly_dark",
                height=400,
                barmode="group",
                margin=dict(l=20, r=20, t=10, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Next-day impact
    st.markdown("**Next-day effect**")
    st.caption("How do metrics look the day *after* a tagged day?")

    next_day_comparison = []
    for metric in available_metrics:
        # Get the day after each tagged day
        next_day_dates = {d + pd.Timedelta(days=1) for d in tagged_dates}
        next_day_data = daily_copy[daily_copy["day"].isin(next_day_dates) & ~daily_copy["tagged"]]
        if len(next_day_data) >= 2:
            nd_mean = next_day_data[metric].mean()
            bl_mean = baseline_days[metric].mean()
            if pd.notna(nd_mean) and pd.notna(bl_mean):
                diff = nd_mean - bl_mean
                next_day_comparison.append({
                    "Metric": FRIENDLY.get(metric, metric),
                    "Day After": round(nd_mean, 1),
                    "Baseline": round(bl_mean, 1),
                    "Difference": round(diff, 1),
                })

    if next_day_comparison:
        st.dataframe(pd.DataFrame(next_day_comparison), use_container_width=True, hide_index=True)
    else:
        st.info("Not enough next-day data for analysis.")
