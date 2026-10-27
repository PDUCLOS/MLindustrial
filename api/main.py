"""API de diagnostic roulement : signal vibratoire brut -> sain / defectueux.

    uvicorn api.main:app --port 8765

Endpoints :
    GET  /                      page de demo (HTML statique, aucun CDN)
    GET  /health                etat du service
    GET  /model                 model card (donnees, metriques CV mesurees)
    GET  /samples               mesures Paderborn reelles embarquees (roulements
                                exclus de l'entrainement du modele servi)
    GET  /samples/{id}          signal (decime pour affichage) + diagnostic
    POST /predict               {"signal": [...], "sampling_rate_hz": 64000}
    POST /predict/features      {"vibration_rms": ..., ...} (5 indicateurs)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.serving.predictor import (  # noqa: E402
    FEATURE_ORDER,
    MIN_SAMPLES,
    PADERBORN_SAMPLING_RATE_HZ,
    BearingDiagnoser,
)

SAMPLES_PATH = ROOT / "models" / "demo_samples.npz"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Diagnostic roulement - Paderborn", version="1.0.0")
diagnoser = BearingDiagnoser()


def _load_samples() -> tuple[dict[str, np.ndarray], list[dict]]:
    data = np.load(SAMPLES_PATH, allow_pickle=False)
    meta = json.loads(str(data["meta"]))
    signals = {m["id"]: data[m["id"]].astype(np.float64) * m["scale"] for m in meta}
    return signals, meta


SAMPLE_SIGNALS, SAMPLE_META = _load_samples()


class SignalIn(BaseModel):
    signal: list[float] = Field(..., min_length=MIN_SAMPLES)
    sampling_rate_hz: int = PADERBORN_SAMPLING_RATE_HZ


class FeaturesIn(BaseModel):
    vibration_crest_factor: float
    vibration_kurtosis: float
    vibration_peak_to_peak: float
    vibration_rms: float
    vibration_skewness: float


def _diagnosis_payload(diag, elapsed_ms: float) -> dict:
    return {
        "label": diag.label,
        "probability_faulty": round(diag.probability_faulty, 4),
        "features": {k: round(v, 5) for k, v in diag.features.items()},
        "baseline_kurtosis": diag.baseline_kurtosis,
        "latency_ms": round(elapsed_ms, 3),
    }


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": diagnoser.card["model_name"], "samples": len(SAMPLE_META)}


@app.get("/model")
def model_card() -> dict:
    return diagnoser.card


@app.get("/samples")
def samples() -> list[dict]:
    return [{k: v for k, v in m.items() if k != "scale"} for m in SAMPLE_META]


@app.get("/samples/{sample_id}")
def sample(sample_id: str, points: int = 2000) -> dict:
    if sample_id not in SAMPLE_SIGNALS:
        raise HTTPException(404, f"echantillon inconnu : {sample_id}")
    x = SAMPLE_SIGNALS[sample_id]
    t0 = time.perf_counter()
    diag = diagnoser.predict_signal(x)
    elapsed = (time.perf_counter() - t0) * 1000
    # 50 ms de signal pour l'affichage (le diagnostic porte sur la mesure complete)
    window = x[: min(len(x), PADERBORN_SAMPLING_RATE_HZ // 20)]
    step = max(1, len(window) // max(points, 1))
    meta = next(m for m in SAMPLE_META if m["id"] == sample_id)
    return {
        "meta": {k: v for k, v in meta.items() if k != "scale"},
        "n_samples": int(len(x)),
        "preview": [round(float(v), 4) for v in window[::step]],
        "preview_ms": round(len(window) / PADERBORN_SAMPLING_RATE_HZ * 1000, 1),
        "diagnosis": _diagnosis_payload(diag, elapsed),
    }


@app.post("/predict")
def predict(body: SignalIn) -> dict:
    if body.sampling_rate_hz != PADERBORN_SAMPLING_RATE_HZ:
        raise HTTPException(
            422,
            f"modele entraine a {PADERBORN_SAMPLING_RATE_HZ} Hz : reechantillonner le signal "
            "avant l'appel (les indicateurs crete/kurtosis dependent de la frequence)",
        )
    t0 = time.perf_counter()
    try:
        diag = diagnoser.predict_signal(np.asarray(body.signal))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _diagnosis_payload(diag, (time.perf_counter() - t0) * 1000)


@app.post("/predict/features")
def predict_features(body: FeaturesIn) -> dict:
    t0 = time.perf_counter()
    diag = diagnoser.predict_features(body.model_dump())
    return _diagnosis_payload(diag, (time.perf_counter() - t0) * 1000)


assert set(FeaturesIn.model_fields) == set(FEATURE_ORDER)
