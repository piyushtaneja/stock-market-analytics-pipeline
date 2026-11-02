"""
Next-session direction model.

Target definition (explicit, for judge Q&A):
    target = 1 if tomorrow's close > today's close, else 0
    (predicted using only information available up to and including "today")

Split: chronological 80/20 — the model NEVER sees future rows during training.
No shuffling. No random train_test_split. This avoids lookahead leakage.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["ma5_ratio", "ma20_ratio", "momentum_5", "volatility_5", "volume_change"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy().sort_values("trade_date").reset_index(drop=True)
    data["ma5_ratio"] = data["close_price"] / data["moving_avg_5"] - 1
    data["ma20_ratio"] = data["close_price"] / data["moving_avg_20"] - 1
    data["momentum_5"] = data["momentum_5"] if "momentum_5" in data else data["close_price"].pct_change(5)
    data["volatility_5"] = data["volatility_5"] if "volatility_5" in data else data["daily_return"].rolling(5).std()
    data["volume_change"] = data["volume_change"] if "volume_change" in data else data["volume"].pct_change()
    # target: did the NEXT trading day close higher than today's close?
    data["target"] = (data["close_price"].shift(-1) > data["close_price"]).astype(int)
    return data


def train_signal_model(df: pd.DataFrame, min_rows: int = 40):
    """
    Returns a dict with the trained model, prediction for the latest row, and
    honest evaluation metrics — or a dict with `error` set if data is insufficient.
    """
    data = build_features(df)
    model_df = data.dropna(subset=FEATURES + ["target"]).copy()

    if len(model_df) < min_rows:
        return {"error": f"Only {len(model_df)} usable rows — need at least {min_rows} for a credible split."}
    if model_df["target"].nunique() < 2:
        return {"error": "Target has only one class in this window — cannot train a classifier."}

    split = int(len(model_df) * 0.8)
    split = max(min(split, len(model_df) - 5), 5)  # keep a real test set on both sides

    train, test = model_df.iloc[:split], model_df.iloc[split:]
    if train["target"].nunique() < 2 or len(test) < 3:
        return {"error": "Chronological split left one side without both classes — need more history."}

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=42, max_iter=1000)),
    ])
    pipe.fit(train[FEATURES], train["target"])

    y_pred = pipe.predict(test[FEATURES])
    y_proba = pipe.predict_proba(test[FEATURES])[:, 1]

    metrics = {
        "accuracy": accuracy_score(test["target"], y_pred),
        "precision": precision_score(test["target"], y_pred, zero_division=0),
        "recall": recall_score(test["target"], y_pred, zero_division=0),
        "f1": f1_score(test["target"], y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(test["target"], y_pred, labels=[0, 1]).tolist(),
        "train_rows": len(train),
        "test_rows": len(test),
    }

    # Latest available row (today) -> predict tomorrow's direction
    latest = data.dropna(subset=FEATURES).iloc[[-1]]
    probability_up = float(pipe.predict_proba(latest[FEATURES])[0, 1])

    coefs = pipe.named_steps["clf"].coef_[0]
    feature_importance = dict(zip(FEATURES, [round(float(c), 4) for c in coefs]))

    return {
        "error": None,
        "probability_up": probability_up,
        "signal": "BULLISH" if probability_up >= 0.5 else "BEARISH",
        "metrics": metrics,
        "feature_importance": feature_importance,
        "as_of_date": str(data["trade_date"].iloc[-1]),
    }
