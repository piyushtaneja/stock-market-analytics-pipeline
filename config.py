"""
Central configuration for the pipeline and dashboard.
Reads from environment variables (loaded from .env if present).
Never hardcode credentials — this module is the single source of truth.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # no-op if .env doesn't exist; real deployments should set env vars directly

MYSQL_CONN_STRING = os.getenv(
    "MYSQL_CONN_STRING",
    "mysql+pymysql://root:@localhost:3306/stockdb",
)

MARKET_API_KEY = os.getenv("MARKET_API_KEY", "").strip()

SYMBOLS = [s.strip() for s in os.getenv(
    "SYMBOLS", "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS"
).split(",") if s.strip()]

DATA_LOOKBACK_PERIOD = os.getenv("DATA_LOOKBACK_PERIOD", "6mo")

# Human-readable label mapping (Yahoo suffix -> display name)
DISPLAY_NAME = {
    "RELIANCE.NS": "RELIANCE",
    "TCS.NS": "TCS",
    "INFY.NS": "INFY",
    "HDFCBANK.NS": "HDFC BANK",
}
