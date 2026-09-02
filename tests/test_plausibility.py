"""Bornes verifiees comme identites mathematiques exactes (pas des heuristiques)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.plausibility import check_plausibility, scan_dataframe
from src.features.time_domain import crest_factor, kurtosis, rms


def test_negative_rms_is_impossible():
    v = check_plausibility("rms", -0.5)
    assert v is not None
    assert v.feature_name == "rms"


def test_zero_rms_is_plausible():
    assert check_plausibility("rms", 0.0) is None


def test_negative_peak_to_peak_is_impossible():
    assert check_plausibility("peak_to_peak", -1.0) is not None


def test_crest_factor_below_one_is_impossible():
    assert check_plausibility("crest_factor", 0.5) is not None


def test_crest_factor_exactly_one_is_plausible():
    # Cas limite : signal constant -> max(|x|) == RMS -> crest_factor == 1.
    assert check_plausibility("crest_factor", 1.0) is None


def test_crest_factor_float_noise_tolerated():
    # 0.999999998 : bruit d'arrondi, pas une vraie violation.
    assert check_plausibility("crest_factor", 0.999999998) is None


def test_kurtosis_below_one_is_impossible():
    assert check_plausibility("kurtosis", 0.5) is not None


def test_kurtosis_gaussian_value_is_plausible():
    assert check_plausibility("kurtosis", 3.0) is None


def test_kurtosis_high_impulsive_value_is_plausible():
    # Pas de borne SUPERIEURE - un signal tres impulsif peut avoir un kurtosis
    # tres eleve (ex. K001 ~14-25 sur Paderborn, voir docs/known_issues.md).
    assert check_plausibility("kurtosis", 50.0) is None


def test_unknown_feature_returns_none_not_a_false_pass():
    # skewness n'a pas de borne universelle definie ici - None signifie "hors
    # perimetre", pas "confirme plausible".
    assert check_plausibility("skewness", -999.0) is None


def test_actual_formulas_never_trigger_their_own_bound():
    # Verification croisee directe : les formules reelles de time_domain.py
    # ne doivent JAMAIS produire une valeur que ce module qualifierait
    # d'impossible, sur des signaux varies (aleatoire, constant, impulsif).
    import numpy as np

    rng = np.random.default_rng(42)
    signals = [
        rng.standard_normal(1000),
        np.ones(1000) * 3.0,  # signal constant -> crest_factor == 1 exactement
        rng.standard_normal(1000) ** 3,  # tres impulsif -> kurtosis eleve
        np.zeros(1000),  # signal nul -> rms=0, crest_factor forcé à 0.0 (cas special code)
    ]
    for x in signals:
        r, c, k = rms(x), crest_factor(x), kurtosis(x)
        assert check_plausibility("rms", r) is None
        assert check_plausibility("kurtosis", k) is None
        # crest_factor(x)==0.0 pour un signal nul (cas special explicite du
        # code, pas une vraie mesure - hors perimetre de ce test physique)
        if r > 0:
            assert check_plausibility("crest_factor", c) is None


def test_scan_dataframe_finds_only_violations():
    df = pd.DataFrame({
        "feature_name": ["rms", "kurtosis", "crest_factor", "rms"],
        "value": [0.3, 14.6, 1.8, -0.1],
        "asset_id": ["K001", "K001", "K001", "KA01"],
    })
    result = scan_dataframe(df)
    assert len(result) == 1
    assert result.iloc[0]["asset_id"] == "KA01"
    assert result.iloc[0]["feature_name"] == "rms"


def test_scan_dataframe_empty_input_returns_empty_not_placeholder():
    result = scan_dataframe(pd.DataFrame(columns=["feature_name", "value"]))
    assert result.empty


def test_scan_dataframe_all_plausible_returns_empty():
    df = pd.DataFrame({
        "feature_name": ["rms", "kurtosis", "crest_factor"],
        "value": [0.3, 14.6, 1.8],
    })
    assert scan_dataframe(df).empty
