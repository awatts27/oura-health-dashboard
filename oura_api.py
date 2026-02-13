"""Oura Ring API v2 client with Streamlit caching."""

import datetime
import streamlit as st
import requests
import pandas as pd

BASE_URL = "https://api.ouraring.com/v2/usercollection"


def _get_token() -> str:
    """Retrieve the Oura Personal Access Token from Streamlit secrets."""
    try:
        return st.secrets["OURA_TOKEN"]
    except KeyError:
        st.error(
            "Oura token not found. Add `OURA_TOKEN` to `.streamlit/secrets.toml`. "
            "See `.streamlit/secrets.toml.example` for the format."
        )
        st.stop()


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}"}


def _fetch_paginated(endpoint: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch all pages from a paginated Oura v2 endpoint."""
    url = f"{BASE_URL}/{endpoint}"
    params = {"start_date": start_date, "end_date": end_date}
    all_data = []

    while url:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        if resp.status_code == 401:
            st.error("Oura API returned 401 Unauthorized. Check your token.")
            st.stop()
        if resp.status_code == 429:
            st.warning("Rate limited by Oura API. Please wait and refresh.")
            st.stop()
        resp.raise_for_status()
        body = resp.json()
        all_data.extend(body.get("data", []))
        next_token = body.get("next_token")
        if next_token:
            params = {"next_token": next_token}
        else:
            url = None

    return all_data


def _date_range(days: int = 90) -> tuple[str, str]:
    """Return (start_date, end_date) strings for the last N days."""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    return start.isoformat(), end.isoformat()


@st.cache_data(ttl=3600, show_spinner="Fetching sleep data from Oura...")
def fetch_daily_sleep(days: int = 90) -> pd.DataFrame:
    """Fetch daily sleep scores."""
    start, end = _date_range(days)
    data = _fetch_paginated("daily_sleep", start, end)
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner="Fetching readiness data from Oura...")
def fetch_daily_readiness(days: int = 90) -> pd.DataFrame:
    """Fetch daily readiness scores."""
    start, end = _date_range(days)
    data = _fetch_paginated("daily_readiness", start, end)
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner="Fetching activity data from Oura...")
def fetch_daily_activity(days: int = 90) -> pd.DataFrame:
    """Fetch daily activity scores."""
    start, end = _date_range(days)
    data = _fetch_paginated("daily_activity", start, end)
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner="Fetching heart rate data from Oura...")
def fetch_heart_rate(days: int = 90) -> pd.DataFrame:
    """Fetch heart rate samples."""
    start, end = _date_range(days)
    data = _fetch_paginated("heartrate", start, end)
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner="Fetching sleep period data from Oura...")
def fetch_sleep_periods(days: int = 90) -> pd.DataFrame:
    """Fetch detailed sleep period data."""
    start, end = _date_range(days)
    data = _fetch_paginated("sleep", start, end)
    if not data:
        return pd.DataFrame()
    df = pd.json_normalize(data)
    for col in ["bedtime_start", "bedtime_end"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"])
        df = df.sort_values("day").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner="Fetching all Oura data...")
def fetch_all_data(days: int = 90) -> dict[str, pd.DataFrame]:
    """Fetch all data sources and return as a dict of DataFrames."""
    return {
        "daily_sleep": fetch_daily_sleep(days),
        "daily_readiness": fetch_daily_readiness(days),
        "daily_activity": fetch_daily_activity(days),
        "heart_rate": fetch_heart_rate(days),
        "sleep_periods": fetch_sleep_periods(days),
    }
