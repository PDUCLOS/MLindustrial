"""Gradient boosting sur features physiques (docs/brief_projet.md section 5-6)."""

import numpy as np
import xgboost as xgb
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score


def train_gbm(X_train: np.ndarray, y_train: np.ndarray, **params) -> xgb.XGBClassifier:
    defaults = dict(n_estimators=200, max_depth=4, learning_rate=0.05, eval_metric="logloss", random_state=42)
    defaults.update(params)
    model = xgb.XGBClassifier(**defaults)
    model.fit(X_train, y_train)
    return model


def evaluate(model: xgb.XGBClassifier, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    pred = model.predict(X_test)
    cm = confusion_matrix(y_test, pred, labels=[0, 1])
    return {
        "f1_macro": float(f1_score(y_test, pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, pred)),
        "confusion_matrix": cm.tolist(),
    }
