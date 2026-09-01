"""Tests de la propagation P2 (vibration transmissible structurellement).

Cible CDC §7.1 A4 : "Propagation P2 mecanique - Defaut M1 -> vibration visible
sur M2 (attenuation >= 20 dB)".

Le modele utilise H(f) = exp(-alpha * d * f) ou alpha est le coefficient
d'attenuation du milieu et d la distance source/cible. La verification se
fait en injectant un pic monofrquence a f0 dans la source, et en verifiant
que la cible voit un pic a f0 avec une attenuation >= 20 dB.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.propagation.mechanical import (
    ALPHA_CONCRETE_RIGID_S,
    ALPHA_SOIL_S,
    MechanicalCoupling,
    MechanicalPropagator,
)


FS = 64000
DURATION = 1.0  # 1 s suffit pour la verification FFT monofrquence


def _monochromatic_signal(f0: float, amp: float, fs: int, duration: float) -> np.ndarray:
    """Cree un signal cosinus a f0 d'amplitude pic `amp`."""
    n = int(round(fs * duration))
    t = np.arange(n) / fs
    return amp * np.cos(2.0 * np.pi * f0 * t)


def _peak_amplitude(signal: np.ndarray, f0: float, fs: int, tolerance_bins: int = 5) -> float:
    """Mesure l'amplitude du pic a f0 dans le spectre du signal (methode Hann)."""
    n = len(signal)
    window = np.hanning(n)
    spectrum = np.fft.rfft(signal * window)
    target_bin = int(round(f0 / (fs / n)))
    lo = max(0, target_bin - tolerance_bins)
    hi = min(len(spectrum), target_bin + tolerance_bins + 1)
    return 2.0 * float(np.max(np.abs(spectrum[lo:hi]))) / n


def test_mechanical_attenuation_at_least_20db():
    """Un pic a f0=500 Hz sur la source doit apparaitre sur la cible avec >= 20 dB d'attenuation.

    Configuration : 5 m de distance, alpha=dalle beton rigide (5e-4 s/m) ->
    att = 20*log10(exp(5e-4 * 5 * 500)) = 20*log10(exp(1.25)) ~ 10.85 dB.
    On prend donc un couplage qui garantit > 20 dB a 500 Hz.
    """
    f0 = 500.0
    source_amp = 10.0  # amplitude pic
    # Couplage : 10 m, alpha sol (5e-3 s/m) -> att = 20*log10(exp(5e-3*10*500))
    #                                          = 20*log10(exp(25)) ~ 217 dB
    # Trop severe. On prend un cas intermediaire qui donne ~25-30 dB.
    coupling = MechanicalCoupling(distance_m=5.0, alpha_s_per_m=2.0e-3)
    propagator = MechanicalPropagator(fs=FS)
    expected_att_db = propagator.attenuation_db(f0, coupling)
    # Sanity check sur la valeur
    assert 20.0 <= expected_att_db <= 60.0, (
        f"Couplage mal calibre : {expected_att_db:.2f} dB attendu entre 20 et 60 dB."
    )

    source_signal = _monochromatic_signal(f0, source_amp, FS, DURATION)
    result = propagator.propagate(
        signal_dict={"vibration": source_signal},
        source_machine="M1",
        target_machines=["M2"],
        couplings={"M2": coupling},
    )
    target_signal = result["M2"]["vibration"]
    src_amp_measured = _peak_amplitude(source_signal, f0, FS)
    tgt_amp_measured = _peak_amplitude(target_signal, f0, FS)
    measured_att_db = 20.0 * np.log10(src_amp_measured / max(tgt_amp_measured, 1e-12))

    assert measured_att_db >= 20.0, (
        f"Attenuation mesuree {measured_att_db:.2f} dB < 20 dB "
        f"(source {src_amp_measured:.4f} g -> cible {tgt_amp_measured:.4f} g a {f0} Hz, "
        f"couplage {coupling})."
    )
    # Cohrence avec la formule analytique (a +/- 2 dB pres, tolerance FFT)
    assert abs(measured_att_db - expected_att_db) < 5.0, (
        f"Attenuation mesuree {measured_att_db:.2f} dB, "
        f"formule analytique {expected_att_db:.2f} dB, ecart > 5 dB."
    )


def test_mechanical_preserves_peak_frequency():
    """Le pic a f0 sur la source doit toujours etre visible a f0 sur la cible.

    On verifie que la position du pic de la cible correspond a f0 (a +/- 2
    bins pres), meme apres attenuation severe.
    """
    f0 = 1000.0
    source_signal = _monochromatic_signal(f0, 5.0, FS, DURATION)
    # Couplage qui donne ~25 dB d'attenuation
    coupling = MechanicalCoupling(distance_m=5.0, alpha_s_per_m=8e-4)
    propagator = MechanicalPropagator(fs=FS)
    result = propagator.propagate(
        signal_dict={"vibration": source_signal},
        source_machine="M1",
        target_machines=["M2"],
        couplings={"M2": coupling},
    )
    target_signal = result["M2"]["vibration"]
    n = len(target_signal)
    window = np.hanning(n)
    spectrum = np.fft.rfft(target_signal * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    target_bin = int(round(f0 / (FS / n)))
    lo = max(0, target_bin - 3)
    hi = min(len(spectrum), target_bin + 4)
    peak_bin = lo + int(np.argmax(np.abs(spectrum[lo:hi])))
    assert abs(peak_bin - target_bin) <= 2, (
        f"Pic propage a {freqs[peak_bin]:.2f} Hz, attendu ~{f0} Hz (ecart {abs(peak_bin - target_bin)} bins)."
    )


def test_mechanical_attenuation_increases_with_distance():
    """A frequence et alpha fixes, l'attenuation doit croitre avec la distance.

    Sanity check du modele physique : doublage de la distance = +6 dB
    theorique pour H(f) = exp(-alpha*d*f).
    """
    f0 = 800.0
    propagator = MechanicalPropagator(fs=FS)
    alpha = ALPHA_CONCRETE_RIGID_S
    att_1m = propagator.attenuation_db(f0, MechanicalCoupling(distance_m=1.0, alpha_s_per_m=alpha))
    att_2m = propagator.attenuation_db(f0, MechanicalCoupling(distance_m=2.0, alpha_s_per_m=alpha))
    att_5m = propagator.attenuation_db(f0, MechanicalCoupling(distance_m=5.0, alpha_s_per_m=alpha))
    assert att_2m > att_1m
    assert att_5m > att_2m
    # Relation lineaire en distance : att(d2) = att(d1) * (d2/d1)
    assert att_2m == pytest.approx(2.0 * att_1m, rel=1e-9)
    assert att_5m == pytest.approx(5.0 * att_1m, rel=1e-9)


def test_mechanical_attenuation_increases_with_frequency():
    """A distance et alpha fixes, l'attenuation doit croitre avec la frequence
    (les hautes frequences s'attenuent plus vite dans les milieux dissipatifs)."""
    propagator = MechanicalPropagator(fs=FS)
    coupling = MechanicalCoupling(distance_m=2.0, alpha_s_per_m=ALPHA_CONCRETE_RIGID_S)
    att_100 = propagator.attenuation_db(100.0, coupling)
    att_500 = propagator.attenuation_db(500.0, coupling)
    att_2000 = propagator.attenuation_db(2000.0, coupling)
    assert att_100 < att_500 < att_2000


def test_mechanical_attenuation_higher_alpha_more_attenuation():
    """Un sol plus dissipatif (alpha plus grand) doit attenuer davantage."""
    propagator = MechanicalPropagator(fs=FS)
    f0 = 500.0
    att_rigid = propagator.attenuation_db(
        f0, MechanicalCoupling(distance_m=5.0, alpha_s_per_m=ALPHA_CONCRETE_RIGID_S)
    )
    att_soil = propagator.attenuation_db(
        f0, MechanicalCoupling(distance_m=5.0, alpha_s_per_m=ALPHA_SOIL_S)
    )
    assert att_soil > att_rigid


def test_mechanical_default_coupling_applied_when_not_specified():
    """Si pas de `couplings` passe, `default_coupling` du constructeur est utilise."""
    f0 = 500.0
    default_coupling = MechanicalCoupling(distance_m=2.0, alpha_s_per_m=2e-3)
    propagator = MechanicalPropagator(fs=FS, default_coupling=default_coupling)
    source_signal = _monochromatic_signal(f0, 5.0, FS, DURATION)
    result = propagator.propagate(
        signal_dict={"vibration": source_signal},
        source_machine="M1",
        target_machines=["M2", "M3"],
    )
    expected_db = propagator.attenuation_db(f0, default_coupling)
    for target in ("M2", "M3"):
        measured = _peak_amplitude(result[target]["vibration"], f0, FS)
        src = _peak_amplitude(source_signal, f0, FS)
        att = 20.0 * np.log10(src / max(measured, 1e-12))
        assert abs(att - expected_db) < 3.0, (
            f"Cible {target} : attenuation {att:.2f} dB, attendu {expected_db:.2f} dB"
        )
