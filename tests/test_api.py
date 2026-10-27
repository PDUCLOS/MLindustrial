"""Tests de l'API de diagnostic (api/main.py) sur le modele et les mesures reelles exportes.

Aucune donnee inventee : les signaux sont les mesures Paderborn embarquees dans
models/demo_samples.npz (roulements tenus a l'ecart de l'entrainement).
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import SAMPLE_SIGNALS, app
from src.serving.predictor import FEATURE_ORDER, MIN_SAMPLES


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_model_card_feature_order(client):
    card = client.get("/model").json()
    assert card["feature_order"] == FEATURE_ORDER
    assert set(card["trained_on"]["held_out_bearings"]) == {"K006", "KI08", "KA22"}


def test_samples_are_held_out(client):
    samples = client.get("/samples").json()
    assert len(samples) == 6
    assert all(s["seen_in_training"] is False for s in samples)
    held_out = set(client.get("/model").json()["trained_on"]["held_out_bearings"])
    assert {s["bearing"] for s in samples} == held_out


def test_sample_endpoint_matches_predict(client):
    sid = next(iter(SAMPLE_SIGNALS))
    via_sample = client.get(f"/samples/{sid}").json()["diagnosis"]
    via_predict = client.post(
        "/predict", json={"signal": SAMPLE_SIGNALS[sid].tolist(), "sampling_rate_hz": 64000}
    ).json()
    assert via_sample["probability_faulty"] == via_predict["probability_faulty"]


def test_predict_features_consistent_with_signal(client):
    sid = next(iter(SAMPLE_SIGNALS))
    diag = client.get(f"/samples/{sid}").json()["diagnosis"]
    r = client.post("/predict/features", json=diag["features"])
    assert r.status_code == 200
    assert abs(r.json()["probability_faulty"] - diag["probability_faulty"]) < 1e-3


def test_rejects_wrong_sampling_rate(client):
    r = client.post("/predict", json={"signal": [0.0] * MIN_SAMPLES, "sampling_rate_hz": 48000})
    assert r.status_code == 422


def test_rejects_short_signal(client):
    r = client.post("/predict", json={"signal": [0.1] * 100})
    assert r.status_code == 422


def test_unknown_sample_404(client):
    assert client.get("/samples/inconnu").status_code == 404


def test_probability_in_unit_interval(client):
    for sid in SAMPLE_SIGNALS:
        p = client.get(f"/samples/{sid}").json()["diagnosis"]["probability_faulty"]
        assert 0.0 <= p <= 1.0
        assert np.isfinite(p)
