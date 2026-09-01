import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.speed import (
    is_variable_speed,
    mean_speed_rpm,
    speed_coefficient_of_variation,
    speed_features,
)


def test_mean_speed_rpm_constant():
    x = np.full(1000, 1500.0)
    assert mean_speed_rpm(x) == pytest.approx(1500.0)


def test_speed_cv_zero_on_constant_speed():
    x = np.full(1000, 1500.0)
    assert speed_coefficient_of_variation(x) == pytest.approx(0.0)


def test_speed_cv_matches_paderborn_observed_order_of_magnitude():
    # Vitesse quasi constante observee sur Paderborn (mean~1499.6, std~0.12 rpm),
    # voir docs/data_model.md - CV attendu de l'ordre de 1e-4, tres en dessous
    # du seuil de detection.
    rng = np.random.default_rng(0)
    x = 1499.6 + rng.normal(scale=0.12, size=16_000)
    cv = speed_coefficient_of_variation(x)
    assert 1e-5 < cv < 1e-3


def test_is_variable_speed_false_below_threshold():
    x = np.full(1000, 1500.0) + np.random.default_rng(1).normal(scale=0.1, size=1000)
    assert is_variable_speed(x) is False


def test_is_variable_speed_true_above_threshold():
    # CV ~10% - nettement au-dessus du seuil par defaut (1%)
    rng = np.random.default_rng(2)
    x = 1500.0 + rng.normal(scale=150.0, size=1000)
    assert is_variable_speed(x) is True


def test_is_variable_speed_respects_custom_threshold():
    x = 1500.0 + np.random.default_rng(3).normal(scale=30.0, size=1000)  # CV ~2%
    assert is_variable_speed(x, cv_threshold=0.05) is False
    assert is_variable_speed(x, cv_threshold=0.01) is True


def test_speed_features_returns_all_keys():
    x = np.full(500, 900.0)
    features = speed_features(x)
    assert set(features.keys()) == {"mean_rpm", "speed_cv", "is_variable_speed"}
    assert features["mean_rpm"] == pytest.approx(900.0)
    assert features["is_variable_speed"] == 0.0


def test_speed_cv_zero_mean_does_not_divide_by_zero():
    x = np.zeros(100)
    assert speed_coefficient_of_variation(x) == 0.0
