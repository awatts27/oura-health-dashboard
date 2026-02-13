# Oura Health Dashboard

Personal health analytics dashboard built with Streamlit and the Oura Ring API v2. Goes beyond the native Oura app with long-term trends, correlation analysis, sleep consistency tracking, and more.

## Features

- **Overview** — KPI cards with latest scores, trend indicators, and 7-day summary
- **Long-term Trends** — Rolling 30/60/90-day moving averages for HRV, resting HR, sleep score, readiness score with trend direction indicators
- **Correlation Analysis** — Interactive scatter plots between any two metrics with R/R² values, pre-built pairs, and a full correlation matrix heatmap
- **Day-of-Week Patterns** — Heatmap and bar charts showing average metrics by day with automatic best/worst day detection
- **Sleep Consistency** — Bedtime/wake time charts, sleep midpoint drift, social jet lag calculation (weekday vs weekend timing)
- **Monthly Report Cards** — Summary stats, streaks, month-over-month deltas, and a composite health trend grade
- **Personal Tags** — Tag days with labels (alcohol, travel, stress, etc.) and see before/after impact analysis including next-day effects

## Setup

### 1. Clone and install dependencies

```bash
git clone <this-repo>
cd oura-health-dashboard
pip install -r requirements.txt
```

### 2. Get your Oura Personal Access Token

1. Go to https://cloud.ouraring.com/personal-access-tokens
2. Create a new token
3. Copy the token

### 3. Configure secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and paste your token:

```toml
OURA_TOKEN = "your_actual_token_here"
```

**Do not commit `secrets.toml` to version control.** It is already in `.gitignore`.

### 4. Run the dashboard

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

## Project Structure

```
oura-health-dashboard/
├── app.py                          # Main entry point and Overview page
├── oura_api.py                     # Oura API v2 client with caching
├── data_processing.py              # Data transformations and analytics
├── pages/
│   ├── 1_Long_Term_Trends.py       # Rolling averages and trend detection
│   ├── 2_Correlation_Analysis.py   # Scatter plots and correlation stats
│   ├── 3_Day_of_Week_Patterns.py   # Heatmap and day-of-week breakdowns
│   ├── 4_Sleep_Consistency.py      # Bedtime consistency and social jet lag
│   ├── 5_Monthly_Report_Cards.py   # Monthly summaries, streaks, grades
│   └── 6_Personal_Tags.py         # Day tagging and impact analysis
├── data/
│   └── tags.json                   # Personal tags (created at runtime)
├── .streamlit/
│   ├── config.toml                 # Dark theme and server config
│   └── secrets.toml.example        # Template for API token
├── requirements.txt
└── README.md
```

## Data Sources

The dashboard pulls from these Oura API v2 endpoints:

| Endpoint | Data |
|----------|------|
| `/v2/usercollection/daily_sleep` | Daily sleep scores and contributors |
| `/v2/usercollection/daily_readiness` | Daily readiness scores and contributors |
| `/v2/usercollection/daily_activity` | Steps, calories, activity scores |
| `/v2/usercollection/heartrate` | Heart rate samples (used for resting HR) |
| `/v2/usercollection/sleep` | Detailed sleep periods (bedtime, wake time) |

API data is cached for 1 hour via `st.cache_data`. Use the "Clear cache & reload" button in the sidebar to force a refresh.

## Tech Stack

- **Streamlit** — UI framework
- **Plotly** — Interactive charts
- **Pandas / NumPy** — Data processing
- **SciPy** — Statistical analysis (correlations, trend detection)
