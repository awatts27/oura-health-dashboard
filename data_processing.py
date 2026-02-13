"""Data transformations and analytics for Oura health data."""

import pandas as pd
import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Merged daily DataFrame
# ---------------------------------------------------------------------------

def build_daily_df(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge daily sleep, readiness, and activity into a single daily DataFrame."""
    frames = []

    sleep = data.get("daily_sleep", pd.DataFrame())
    if not sleep.empty and "day" in sleep.columns:
        cols = {"day": "day"}
        if "score" in sleep.columns:
            cols["score"] = "sleep_score"
        for c in sleep.columns:
            if c.startswith("contributors."):
                cols[c] = f"sleep_{c.replace('contributors.', '')}"
        frames.append(sleep.rename(columns=cols)[list(cols.values())])

    readiness = data.get("daily_readiness", pd.DataFrame())
    if not readiness.empty and "day" in readiness.columns:
        cols = {"day": "day"}
        if "score" in readiness.columns:
            cols["score"] = "readiness_score"
        for c in readiness.columns:
            if c.startswith("contributors."):
                cols[c] = f"readiness_{c.replace('contributors.', '')}"
        frames.append(readiness.rename(columns=cols)[list(cols.values())])

    activity = data.get("daily_activity", pd.DataFrame())
    if not activity.empty and "day" in activity.columns:
        cols = {"day": "day"}
        if "score" in activity.columns:
            cols["score"] = "activity_score"
        for c in ["steps", "total_calories", "active_calories",
                   "equivalent_walking_distance", "high_activity_time",
                   "medium_activity_time", "low_activity_time",
                   "sedentary_time", "met.average", "met.high", "met.low"]:
            if c in activity.columns:
                cols[c] = c.replace(".", "_")
        frames.append(activity.rename(columns=cols)[list(cols.values())])

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="day", how="outer")

    merged = merged.sort_values("day").reset_index(drop=True)
    merged["day_of_week"] = merged["day"].dt.day_name()
    merged["week_number"] = merged["day"].dt.isocalendar().week.astype(int)
    merged["month"] = merged["day"].dt.to_period("M").astype(str)
    merged["is_weekend"] = merged["day"].dt.dayofweek >= 5
    return merged


# ---------------------------------------------------------------------------
# Heart rate daily aggregates
# ---------------------------------------------------------------------------

def daily_hr_stats(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate heart rate samples into daily stats (resting-source only)."""
    hr = data.get("heart_rate", pd.DataFrame())
    if hr.empty or "timestamp" not in hr.columns:
        return pd.DataFrame()

    hr = hr.copy()
    hr["day"] = hr["timestamp"].dt.date
    # Use rest source for resting HR / HRV proxy
    if "source" in hr.columns:
        rest = hr[hr["source"] == "rest"]
    else:
        rest = hr

    if rest.empty:
        rest = hr

    agg = rest.groupby("day").agg(
        resting_hr=("bpm", "min"),
        avg_hr=("bpm", "mean"),
        hr_samples=("bpm", "count"),
    ).reset_index()
    agg["day"] = pd.to_datetime(agg["day"])
    return agg


# ---------------------------------------------------------------------------
# Sleep period enrichment
# ---------------------------------------------------------------------------

def enrich_sleep_periods(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Add bedtime/wake time hours and midpoint to sleep periods."""
    sp = data.get("sleep_periods", pd.DataFrame())
    if sp.empty:
        return pd.DataFrame()

    sp = sp.copy()

    if "bedtime_start" in sp.columns:
        sp["bedtime_hour"] = (
            sp["bedtime_start"].dt.hour + sp["bedtime_start"].dt.minute / 60
        )
        # Wrap hours past midnight so 23:00 = 23, 00:30 = 24.5
        sp["bedtime_hour_adj"] = sp["bedtime_hour"].apply(
            lambda h: h if h >= 12 else h + 24
        )

    if "bedtime_end" in sp.columns:
        sp["waketime_hour"] = (
            sp["bedtime_end"].dt.hour + sp["bedtime_end"].dt.minute / 60
        )

    if "bedtime_hour_adj" in sp.columns and "waketime_hour" in sp.columns:
        sp["sleep_midpoint"] = (sp["bedtime_hour_adj"] + sp["waketime_hour"]) / 2
        # Normalize back to 0-24
        sp["sleep_midpoint"] = sp["sleep_midpoint"] % 24

    # Filter to long_sleep type if available
    if "type" in sp.columns:
        sp = sp[sp["type"] == "long_sleep"]

    return sp


# ---------------------------------------------------------------------------
# Rolling averages
# ---------------------------------------------------------------------------

def add_rolling_averages(
    df: pd.DataFrame,
    columns: list[str],
    windows: list[int] = (7, 30, 60, 90),
) -> pd.DataFrame:
    """Add rolling mean columns for the specified metrics and windows."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        for w in windows:
            df[f"{col}_ma{w}"] = (
                df[col].rolling(window=w, min_periods=max(1, w // 3)).mean()
            )
    return df


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

def compute_trend(series: pd.Series, window: int = 30) -> str:
    """Determine if the last `window` values are improving, declining, or stable.

    Uses linear regression slope relative to mean.
    """
    recent = series.dropna().tail(window)
    if len(recent) < 7:
        return "insufficient data"

    x = np.arange(len(recent))
    slope, _, _, _, _ = stats.linregress(x, recent.values)
    mean_val = recent.mean()
    if mean_val == 0:
        return "stable"
    relative_slope = slope / mean_val

    if relative_slope > 0.002:
        return "improving"
    elif relative_slope < -0.002:
        return "declining"
    return "stable"


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------

def compute_correlation(
    df: pd.DataFrame, col_a: str, col_b: str
) -> tuple[float, float, int]:
    """Return (r_value, p_value, n) for two columns."""
    subset = df[[col_a, col_b]].dropna()
    n = len(subset)
    if n < 5:
        return (np.nan, np.nan, n)
    r, p = stats.pearsonr(subset[col_a], subset[col_b])
    return (r, p, n)


# ---------------------------------------------------------------------------
# Day-of-week aggregation
# ---------------------------------------------------------------------------

def day_of_week_stats(
    df: pd.DataFrame, metrics: list[str]
) -> pd.DataFrame:
    """Return mean of metrics grouped by day of week, ordered Mon-Sun."""
    if df.empty or "day_of_week" not in df.columns:
        return pd.DataFrame()

    day_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    existing = [m for m in metrics if m in df.columns]
    if not existing:
        return pd.DataFrame()

    agg = df.groupby("day_of_week")[existing].mean()
    agg = agg.reindex(day_order).reset_index()
    return agg


# ---------------------------------------------------------------------------
# Sleep consistency / social jet lag
# ---------------------------------------------------------------------------

def sleep_consistency_stats(sp: pd.DataFrame) -> dict:
    """Compute social jet lag and bedtime consistency metrics."""
    result: dict = {}
    if sp.empty:
        return result

    if "is_weekend" not in sp.columns and "day" in sp.columns:
        sp = sp.copy()
        sp["is_weekend"] = sp["day"].dt.dayofweek >= 5

    if "bedtime_hour_adj" in sp.columns:
        result["bedtime_std_hrs"] = sp["bedtime_hour_adj"].std()

    if "waketime_hour" in sp.columns:
        result["waketime_std_hrs"] = sp["waketime_hour"].std()

    if "sleep_midpoint" in sp.columns and "is_weekend" in sp.columns:
        wkday = sp.loc[~sp["is_weekend"], "sleep_midpoint"].mean()
        wkend = sp.loc[sp["is_weekend"], "sleep_midpoint"].mean()
        if pd.notna(wkday) and pd.notna(wkend):
            result["social_jet_lag_hrs"] = abs(wkend - wkday)
            result["weekday_midpoint"] = wkday
            result["weekend_midpoint"] = wkend

    return result


# ---------------------------------------------------------------------------
# Monthly report card helpers
# ---------------------------------------------------------------------------

def monthly_summary(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    """Compute monthly averages, min, max for given metrics."""
    if df.empty or "month" not in df.columns:
        return pd.DataFrame()

    existing = [m for m in metrics if m in df.columns]
    if not existing:
        return pd.DataFrame()

    agg_funcs = {}
    for m in existing:
        agg_funcs[f"{m}_mean"] = (m, "mean")
        agg_funcs[f"{m}_min"] = (m, "min")
        agg_funcs[f"{m}_max"] = (m, "max")
        agg_funcs[f"{m}_std"] = (m, "std")

    summary = df.groupby("month").agg(**agg_funcs).reset_index()
    return summary


def compute_streaks(series: pd.Series, threshold: float) -> dict:
    """Compute current and longest streak of days above threshold."""
    above = series.dropna() >= threshold
    current = 0
    longest = 0
    streak = 0
    for val in above:
        if val:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    current = streak
    return {"current_streak": current, "longest_streak": longest}


def health_trend_grade(df: pd.DataFrame) -> str:
    """Simple composite health trend grade based on key metrics."""
    trends = []
    for col in ["sleep_score", "readiness_score", "resting_hr"]:
        if col in df.columns:
            t = compute_trend(df[col])
            if col == "resting_hr":
                # Lower resting HR is better, so invert
                t = {"improving": "declining", "declining": "improving"}.get(t, t)
            trends.append(t)

    if not trends:
        return "N/A"

    improving = trends.count("improving")
    declining = trends.count("declining")

    if improving > declining:
        return "Improving"
    elif declining > improving:
        return "Declining"
    return "Stable"
