"""Inference du modele de diagnostic roulement (vibration seule).

Le modele servi est exactement celui de la Phase 2 (scripts/run_gbm.py,
sensor set `vibration_only`) : XGBoost sur les 5 indicateurs temporels du
canal vibration, reentraine sur les 32 roulements par scripts/export_model.py.
Les features sont recalculees ici avec la MEME fonction que le pipeline
d'ingestion (src.features.time_domain) : pas de reimplementation divergente
entre entrainement et service.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xgboost as xgb

from src.features.time_domain import time_domain_features

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
# Ordre exact des colonnes a l'entrainement (pivot trie alphabetiquement dans run_gbm.py)
FEATURE_ORDER = [
    "vibration_crest_factor",
    "vibration_kurtosis",
    "vibration_peak_to_peak",
    "vibration_rms",
    "vibration_skewness",
]
PADERBORN_SAMPLING_RATE_HZ = 64_000
MIN_SAMPLES = 4_096


@dataclass
class Diagnosis:
    label: str
    probability_faulty: float
    features: dict[str, float]
    baseline_kurtosis: dict


class BearingDiagnoser:
    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        self.card = json.loads((model_dir / "model_card.json").read_text(encoding="utf-8"))
        if self.card["feature_order"] != FEATURE_ORDER:
            raise ValueError("feature_order du model_card incompatible avec le service")
        # Booster natif plutot que XGBClassifier : meme modele, mais sans
        # dependance a scikit-learn dans l'image de service.
        self.model = xgb.Booster()
        self.model.load_model(str(model_dir / "gbm_vibration.json"))

    def features_from_signal(self, signal: np.ndarray) -> dict[str, float]:
        x = np.asarray(signal, dtype=np.float64)
        if x.ndim != 1 or x.size < MIN_SAMPLES:
            raise ValueError(f"signal 1D d'au moins {MIN_SAMPLES} echantillons attendu")
        if not np.all(np.isfinite(x)):
            raise ValueError("signal contenant des valeurs non finies")
        return {f"vibration_{k}": v for k, v in time_domain_features(x).items()}

    def predict_features(self, features: dict[str, float]) -> Diagnosis:
        row = np.array([[features[name] for name in FEATURE_ORDER]])
        proba = float(self.model.predict(xgb.DMatrix(row))[0])  # objective binary:logistic
        base = self.card["baseline_kurtosis"]
        kurt = features["vibration_kurtosis"]
        if base["direction"] == "lower_is_faulty":
            base_faulty = kurt <= base["threshold"]
        else:
            base_faulty = kurt >= base["threshold"]
        return Diagnosis(
            label="faulty" if proba >= 0.5 else "healthy",
            probability_faulty=proba,
            features=features,
            baseline_kurtosis={**base, "prediction": "faulty" if base_faulty else "healthy"},
        )

    def predict_signal(self, signal: np.ndarray) -> Diagnosis:
        return self.predict_features(self.features_from_signal(signal))
