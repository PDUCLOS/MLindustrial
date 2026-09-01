"""Tests de sanite sur les indicateurs temporels (docs/brief_projet.md section 6).

Objectif specifique : un test "kurtosis gaussien ~3, signal impulsif > gaussien"
aurait probablement detecte plus tot le motif kurtosis inverse documente dans
docs/known_issues.md (sain > defaut sur Paderborn) - absence de ce test de
sanite = trou reel identifie 2026-09-01.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.time_domain import (
    crest_factor,
    kurtosis,
    peak_to_peak,
    rms,
    skewness,
    time_domain_features,
)


def test_rms_constant_signal():
    x = np.full(1000, 3.0)
    assert rms(x) == pytest.approx(3.0)


def test_rms_sine_wave():
    # RMS d'un sinus d'amplitude A = A/sqrt(2)
    t = np.linspace(0, 10, 100_000, endpoint=False)
    x = 5.0 * np.sin(2 * np.pi * 7 * t)
    assert rms(x) == pytest.approx(5.0 / np.sqrt(2), rel=1e-3)


def test_peak_to_peak_known_array():
    x = np.array([-2.0, 0.0, 3.0, 1.0])
    assert peak_to_peak(x) == pytest.approx(5.0)


def test_crest_factor_sine_wave():
    # Facteur de crete d'un sinus pur = sqrt(2) ~ 1.4142, independant de l'amplitude
    t = np.linspace(0, 10, 100_000, endpoint=False)
    x = 5.0 * np.sin(2 * np.pi * 7 * t)
    assert crest_factor(x) == pytest.approx(np.sqrt(2), rel=1e-3)


def test_crest_factor_zero_signal_returns_zero_not_nan():
    x = np.zeros(100)
    assert crest_factor(x) == 0.0


def test_kurtosis_gaussian_noise_near_three():
    # Convention vibratoire (fisher=False) : gaussien -> kurtosis ~= 3
    rng = np.random.default_rng(42)
    x = rng.normal(size=200_000)
    assert kurtosis(x) == pytest.approx(3.0, abs=0.1)


def test_kurtosis_impulsive_signal_exceeds_gaussian():
    # Signal majoritairement plat avec quelques impulsions rares - typique
    # d'un defaut roulement actif. Doit etre NETTEMENT plus impulsif (kurtosis
    # plus eleve) qu'un bruit gaussien de meme variance globale.
    rng = np.random.default_rng(0)
    n = 100_000
    baseline = rng.normal(scale=0.1, size=n)
    impulse_idx = rng.choice(n, size=n // 200, replace=False)  # 0.5% d'impulsions
    baseline[impulse_idx] += rng.normal(scale=3.0, size=len(impulse_idx))

    gaussian = rng.normal(scale=np.std(baseline), size=n)

    k_impulsive = kurtosis(baseline)
    k_gaussian = kurtosis(gaussian)

    assert k_impulsive > k_gaussian
    assert k_impulsive > 3.5  # nettement au-dessus du plateau gaussien ~3


def test_skewness_symmetric_signal_near_zero():
    t = np.linspace(0, 10, 100_000, endpoint=False)
    x = np.sin(2 * np.pi * 7 * t)
    assert skewness(x) == pytest.approx(0.0, abs=0.05)


def test_skewness_asymmetric_signal_nonzero():
    # Distribution log-normale : fortement asymetrique a droite par construction
    rng = np.random.default_rng(1)
    x = rng.lognormal(mean=0, sigma=1.0, size=50_000)
    assert skewness(x) > 1.0


def test_time_domain_features_returns_all_five_keys():
    x = np.random.default_rng(2).normal(size=1000)
    features = time_domain_features(x)
    assert set(features.keys()) == {"rms", "peak_to_peak", "crest_factor", "kurtosis", "skewness"}
    assert all(np.isfinite(v) for v in features.values())
