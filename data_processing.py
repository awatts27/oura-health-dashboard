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

    for col in ["bedtime_start", "bedtime_end"]:
        if col in sp.columns:
            sp[col] = pd.to_datetime(sp[col], utc=True, errors="coerce")

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


def compute_trend_detail(series: pd.Series, window: int = 30) -> dict:
    """Return detailed trend info: direction, total change, and per-day slope."""
    recent = series.dropna().tail(window)
    n = len(recent)
    if n < 7:
        return {"direction": "insufficient data", "change": 0.0, "slope_per_day": 0.0, "days": n}

    x = np.arange(n)
    slope, intercept, _, _, _ = stats.linregress(x, recent.values)
    total_change = slope * (n - 1)
    return {
        "direction": compute_trend(series, window),
        "change": round(total_change, 1),
        "slope_per_day": round(slope, 2),
        "days": n,
    }


def generate_key_findings(daily: pd.DataFrame, sleep_periods: pd.DataFrame = None) -> list[str]:
    """Generate plain-language key findings from the data."""
    findings = []

    # 1. Biggest recent change in any core metric
    METRICS = {
        "sleep_score": "Sleep score",
        "readiness_score": "Readiness score",
        "activity_score": "Activity score",
        "resting_hr": "Resting heart rate",
        "steps": "Daily steps",
    }
    biggest_change = None
    biggest_abs = 0
    for col, label in METRICS.items():
        if col not in daily.columns:
            continue
        detail = compute_trend_detail(daily[col], window=21)
        if detail["direction"] == "insufficient data":
            continue
        if abs(detail["change"]) > biggest_abs:
            biggest_abs = abs(detail["change"])
            biggest_change = (col, label, detail)

    if biggest_change:
        col, label, detail = biggest_change
        direction = "up" if detail["change"] > 0 else "down"
        verb = "climbed" if detail["change"] > 0 else "dropped"
        # For resting HR, direction meaning is inverted
        if col == "resting_hr":
            qualifier = " (higher is worse)" if detail["change"] > 0 else " (lower is better)"
        else:
            qualifier = ""
        findings.append(
            f"**{label}** has {verb} ~{abs(detail['change']):.0f} points over the last "
            f"{detail['days']} days{qualifier}."
        )

    # 2. Best and worst day of week for sleep
    if "day_of_week" in daily.columns and "sleep_score" in daily.columns:
        dow = daily.groupby("day_of_week")["sleep_score"].mean()
        if len(dow) >= 5:
            best = dow.idxmax()
            worst = dow.idxmin()
            gap = dow.max() - dow.min()
            if gap > 2:
                findings.append(
                    f"Your best sleep nights are **{best}s** (avg {dow[best]:.0f}) "
                    f"and worst are **{worst}s** (avg {dow[worst]:.0f})."
                )

    # 3. Weekend vs weekday difference
    if "is_weekend" in daily.columns and "sleep_score" in daily.columns:
        wkday_avg = daily.loc[~daily["is_weekend"], "sleep_score"].mean()
        wkend_avg = daily.loc[daily["is_weekend"], "sleep_score"].mean()
        if pd.notna(wkday_avg) and pd.notna(wkend_avg):
            diff = wkend_avg - wkday_avg
            if abs(diff) > 2:
                better = "weekends" if diff > 0 else "weekdays"
                findings.append(
                    f"You sleep **{abs(diff):.1f} points** better on {better}."
                )

    # 4. Resting HR trend warning
    if "resting_hr" in daily.columns:
        hr_detail = compute_trend_detail(daily["resting_hr"], window=14)
        if hr_detail["direction"] == "improving":  # improving = declining for HR
            pass  # already covered above potentially
        elif hr_detail["change"] > 1.5:
            findings.append(
                f"Resting heart rate has risen ~{hr_detail['change']:.0f} bpm over "
                f"the last 2 weeks — worth keeping an eye on."
            )

    # 5. Sleep consistency insight
    if sleep_periods is not None and not sleep_periods.empty and "bedtime_hour_adj" in sleep_periods.columns:
        std = sleep_periods["bedtime_hour_adj"].std()
        if pd.notna(std):
            if std > 1.5:
                findings.append(
                    f"Your bedtime varies by **\u00b1{std:.1f} hours** — "
                    f"high variability can affect sleep quality."
                )
            elif std < 0.5:
                findings.append(
                    f"Your bedtime is very consistent (\u00b1{std:.1f} hrs) — that's great for sleep quality."
                )

    return findings


def interpret_r(r: float) -> str:
    """Return a plain-language interpretation of a Pearson R value."""
    abs_r = abs(r)
    if abs_r < 0.1:
        strength = "negligible"
    elif abs_r < 0.3:
        strength = "weak"
    elif abs_r < 0.5:
        strength = "moderate"
    elif abs_r < 0.7:
        strength = "strong"
    else:
        strength = "very strong"
    direction = "positive" if r > 0 else "negative"
    return f"{strength} {direction} correlation"


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
