"""Kurtogramme consensus vs par-signal (voir docs/known_issues.md).

Scenario reproduit le probleme documente sur K001/KA01/KA04 : un signal du
groupe porte un artefact impulsif dominant a une frequence differente de la
resonance partagee par le reste du groupe. Le kurtogramme par-signal se fait
piloter par cet artefact ; le consensus (moyenne sur le groupe) doit rester
sur la resonance commune.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.envelope import consensus_resonance_band, select_resonance_band

FS = 20000.0
DURATION_S = 1.0
SHARED_RESONANCE_HZ = 3000.0
OUTLIER_RESONANCE_HZ = 7000.0


def _resonant_impulse_train(
    fs: float, duration_s: float, resonance_hz: float, impact_rate_hz: float,
    decay: float = 1200.0, amplitude: float = 1.0, seed: int = 0,
) -> np.ndarray:
    """Train d'impacts qui excitent une resonance fixe - modele simplifie d'un
    choc de defaut de roulement (impact bref -> reponse amortie a f_resonance)."""
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for ti in np.arange(0, duration_s, 1.0 / impact_rate_hz):
        idx0 = int(ti * fs)
        tt = t[idx0:] - ti
        env = amplitude * np.exp(-decay * tt)
        x[idx0:] += env * np.sin(2 * np.pi * resonance_hz * tt)
    x += np.random.default_rng(seed).normal(0, 0.05, n)
    return x


def _make_group_with_outlier() -> list[np.ndarray]:
    signals = [
        _resonant_impulse_train(FS, DURATION_S, SHARED_RESONANCE_HZ, 200.0, seed=i)
        for i in range(5)
    ]
    # signal 0 porte un artefact impulsif plus fort a une frequence differente
    # (ex. transitoire d'accouplement/banc, cf. hypothese 1 docs/known_issues.md)
    signals[0] = signals[0] + _resonant_impulse_train(
        FS, DURATION_S, OUTLIER_RESONANCE_HZ, 350.0, decay=2000.0, amplitude=4.0, seed=99
    )
    return signals


def test_per_signal_kurtogram_is_hijacked_by_outlier():
    # Documente le probleme (pas une garantie de comportement a preserver) :
    # le signal outlier seul se fait piloter par l'artefact, pas la resonance
    # partagee - c'est exactement le motif de docs/known_issues.md.
    signals = _make_group_with_outlier()
    low, high = select_resonance_band(signals[0], FS, min_freq_hz=500.0)
    fc = (low + high) / 2
    assert abs(fc - OUTLIER_RESONANCE_HZ) < abs(fc - SHARED_RESONANCE_HZ)


def test_consensus_recovers_shared_resonance_despite_outlier():
    signals = _make_group_with_outlier()
    result = consensus_resonance_band(signals, FS, min_freq_hz=500.0)
    fc = result["best"]["fc"]
    assert fc == pytest.approx(SHARED_RESONANCE_HZ, abs=200.0)
    assert result["n_signals"] == 5


def test_consensus_tolerates_small_length_mismatch():
    # Gigue d'acquisition reelle observee sur Paderborn (~2%, voir
    # docs/known_issues.md) - doit tronquer, pas planter.
    signals = _make_group_with_outlier()
    signals[1] = signals[1][:-10]
    result = consensus_resonance_band(signals, FS, min_freq_hz=500.0)
    assert result["best"]["fc"] == pytest.approx(SHARED_RESONANCE_HZ, abs=200.0)


def test_consensus_rejects_large_length_mismatch():
    signals = _make_group_with_outlier()
    signals[1] = signals[1][: len(signals[1]) // 2]  # 50% plus court
    with pytest.raises(ValueError, match="ecart de longueur trop grand"):
        consensus_resonance_band(signals, FS, min_freq_hz=500.0)


def test_consensus_rejects_empty_group():
    with pytest.raises(ValueError, match="vide"):
        consensus_resonance_band([], FS, min_freq_hz=500.0)
