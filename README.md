# StockPulse — NSE Market Intelligence & Data Engineering Platform

An automated ETL + ML pipeline for NSE stock data, orchestrated by Apache Airflow,
stored in MySQL, and served through a Streamlit analytics dashboard.

## Architecture

```
yfinance (live) ──┐
                   ├──▶ Extract ──▶ Transform ──▶ Data Quality Check ──▶ MySQL ──▶ Dashboard
demo_fallback ─────┘         (Pandas)      (nulls/price/dupe checks)   (stockdb)   (Streamlit + ML)
        ▲
        └── used ONLY when yfinance fails (rate limit / network) — every row
            is tagged data_source + is_demo so the UI never claims fake data is live
```

Airflow orchestrates the same four ETL functions on a schedule (`@daily`). The
dashboard's "Trigger Ingestion Now" button runs the identical functions
synchronously — useful for a live demo that doesn't depend on the scheduler's
timing.

## Why these choices (for judges)

- **Why Airflow, not just a cron job / script?** Dependency-aware task graph,
  retries, per-task logging, and a UI that visibly proves orchestration —
  the whole point of demonstrating "Data Engineering" rather than a script.
- **Why MySQL, not just CSV/SQLite?** Concurrent read (dashboard) + write
  (pipeline) access, upsert semantics (`ON DUPLICATE KEY UPDATE`), and it's
  what a real analytics backend would use.
- **Why Logistic Regression, not a black-box deep model?** With ~130 rows per
  symbol, a simple, interpretable model (visible coefficients) is honest about
  what the data can support. A complex model here would overfit and its
  "accuracy" would be meaningless.
- **What makes this Data Engineering rather than "just ML"?** The ML step is
  the last 10% — the other 90% is extraction with fallback handling, schema
  design, data-quality gating, and orchestration. The dashboard exposes all of
  that, not just a prediction.

## Data source honesty (read this before your demo)

`yfinance` frequently rate-limits (HTTP 429) from cloud/shared IPs, including
WSL environments hitting it repeatedly during development. When it fails, the
pipeline falls back to a **deterministic, seeded synthetic dataset** — clearly
labeled `data_source = 'demo_fallback'` and `is_demo = TRUE` in MySQL, and
shown as an amber "DEMO / FALLBACK DATA" badge in the dashboard. **Never say
this is live or real market data in your demo** — say it exactly like this
badge does: "this is a fallback because the free API rate-limited us; here's
how the system detects and labels that instead of silently pretending."
Judges respond well to that honesty — it demonstrates you understand
production data-reliability concerns.

If you want a real paid/free-tier API as a second live source, `MARKET_API_KEY`
in `.env` is reserved for that (e.g. Twelve Data) — not wired up by default
since no key was provided; wiring it in is a clean extension to mention under
"future work" if asked.

## Setup

### 1. MySQL (Windows, already running per your setup)
```sql
CREATE DATABASE IF NOT EXISTS stockdb;
```
Then run **`sql/schema.sql`** if this is a fresh database, OR
**`sql/migration_existing_table.sql`** if you're keeping your existing
260-row `stock_prices` table (adds the new columns without dropping data).

### 2. Environment
```bash
cp .env.example .env
# edit .env if your MySQL host/user/password differ from the defaults
```

### 3. Python deps (WSL venv)
```bash
cd ~/stock_pipeline_project        # keep the project INSIDE the WSL filesystem, not /mnt/c/...
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Airflow (WSL, 3.3.2 — already installed per your setup)
```bash
export AIRFLOW_HOME=~/airflow
export AIRFLOW__CORE__HOSTNAME_CALLABLE=airflow.utils.net.get_host_ip_address
airflow standalone
```
Copy/symlink `dags/stock_pipeline_dag.py` into `$AIRFLOW_HOME/dags/` (or point
`AIRFLOW__CORE__DAGS_FOLDER` at this repo's `dags/` directory directly).
Open **http://localhost:8080**, enable `stock_market_pipeline`, trigger it.

If a task still fails with no useful message: the DAG now wraps every task
function so the real traceback is printed to the task log instead of stopping
at "Pre Execute" — open the failed task's log and read the actual exception
(most likely cause: the Airflow worker's Python environment doesn't have
`pymysql`/`yfinance`/`scikit-learn` installed — confirm `airflow` and your venv
are the same Python).

### 5. Dashboard
```bash
streamlit run streamlit_app/app.py
```
Open **http://localhost:8501**

## Demo sequence (3–5 minutes)

1. Open dashboard, select a stock (sidebar) — point out the DEMO/LIVE badge.
2. Show the candlestick chart + MA5/MA20 + volume (Price & Volume tab).
3. Open **Pipeline Health** tab — show `pipeline_run_logs`, explain the stages.
4. Click **Trigger Ingestion Now** — live re-run in front of judges.
5. Open MySQL Workbench, `SELECT * FROM stock_prices ORDER BY inserted_at DESC LIMIT 5;` — prove it's really in the DB.
6. Switch to Airflow UI (localhost:8080), trigger the DAG, show the graph turning green — same pipeline, orchestrated.
7. Back to dashboard → **ML Signal** tab — explain target, chronological split, show accuracy/precision/recall + confusion matrix + coefficients.
8. **Risk Metrics** tab — daily return, volatility, momentum, drawdown.
9. Mention **Trading Sandbox** tab is explicitly a non-connected UI concept, not a fake broker.
10. Close on limitations (below) — shows maturity, not weakness.

## Judge Q&A

| Question | Answer |
|---|---|
| Why Airflow? | Dependency-aware orchestration, retries, logging, visible task graph — not just a script that runs once. |
| Why MySQL? | Concurrent access for pipeline writes + dashboard reads, upsert semantics, relational integrity via unique (symbol, date). |
| Why not just Streamlit? | Streamlit is presentation only — it has no scheduling, no data-quality gate, no persistence layer of its own. |
| Why this ML model? | Interpretable, appropriate for small per-symbol datasets (~130 rows); coefficients are inspectable, unlike a black-box model that would overfit here. |
| What is your target variable? | Binary: next trading day's close > today's close. |
| How do you prevent data leakage? | Strict chronological 80/20 split — no shuffling, no future rows in training, features use only data up to "today". |
| How is data fetched? | `yfinance` daily pull; on failure, a seeded synthetic fallback dataset, both tagged with `data_source`. |
| How frequently? | Daily via the Airflow DAG (`@daily`); also on-demand via the dashboard's Trigger button. |
| What happens if the API fails? | Falls back to a labeled demo dataset — pipeline still completes, quality checks still run, nothing is silently treated as real. |
| What data-quality checks do you perform? | Non-positive prices, negative volume, duplicate (symbol, date) keys, null-ratio threshold on core fields — the load is blocked if these fail. |
| Why moving averages / momentum / volatility? | Standard, well-understood technical features that summarize trend and risk without needing external data. |
| What makes this Data Engineering rather than just ML? | Extraction with fallback handling, schema design, quality gating, and orchestration — the ML step is a small consumer of that pipeline. |
| What makes this MCA-level? | End-to-end system design: orchestration, data quality, honest source labeling, evaluation methodology — not just a single script. |
| What is the limitation? | Small per-symbol history (~130 rows), free-tier data source reliability, single-market (NSE, 4 symbols) scope. |
| Is the prediction guaranteed? | No — it's a probabilistic, educational signal with reported hold-out accuracy; explicitly disclaimed as not investment advice. |
| How would this scale to 100+ stocks? | Parameterize `SYMBOLS` (already env-driven), partition/parallelize Airflow tasks per symbol or batch, add indexing/partitioning on `stock_prices`. |
| How would you deploy it? | Containerize each component (Airflow, MySQL, Streamlit) via Docker Compose; move secrets to a proper secret manager instead of `.env`. |

## Honest limitations

- Free-tier `yfinance` is unreliable under repeated calls (rate limiting) —
  the demo-fallback exists *because of* this, not despite it.
- Only 4 NSE symbols and a few months of history — not enough data for a
  high-confidence model; metrics shown are real but should be read as
  "better than a coin flip, on this small sample," not a trading system.
- No real-time/tick data — this is daily (EOD-equivalent) granularity.
- The "Trading Sandbox" tab is a UI concept only, not a broker integration.
