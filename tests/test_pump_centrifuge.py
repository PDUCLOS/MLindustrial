"""Tests du modele N2 pompe centrifuge 30 kW a 3000 rpm (SA5 CDC Factory Twin Phase A).

Cible : `src/simulation/pump_centrifuge.py::simulate_pump`.

Verification des criteres V1 et V2 de `docs/architecture_usine_simulation.md`
§9.1 adaptes a la pompe :
- V1 : raie a la BPFO du 6206 (a 3000 rpm) presente dans le spectre
  quand le defaut est active
- V2 : RMS vibration sain dans la plage 0.1-5 g
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.fault_frequencies import (
    bpfo,
    rotational_frequency_hz,
)
from src.simulation.pump_centrifuge import (
    CAVITATION_BAND_HZ,
    pump_diagnostic_summary,
    simulate_pump,
)

# Configuration par defaut : 4 s a 64 kHz, aligne Paderborn.
DURATION_S = 4.0
FS = 64000
RPM_TEST = 3000  # vitesse nominale d'une pompe 2 poles 50 Hz


def _rfft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """FFT mono-cote avec normalisation amplitude (pour pic search)."""
    n = len(signal)
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(spectrum) * 2.0 / n
    return freqs, mag


def _peak_in_band(freqs: np.ndarray, mag: np.ndarray, f_center: float, f_half_width: float) -> float:
    band = (freqs >= f_center - f_half_width) & (freqs <= f_center + f_half_width)
    if not np.any(band):
        return 0.0
    return float(np.max(mag[band]))


def _peak_frequency(freqs: np.ndarray, mag: np.ndarray, f_center: float, f_half_width: float) -> float:
    band = (freqs >= f_center - f_half_width) & (freqs <= f_center + f_half_width)
    if not np.any(band):
        return 0.0
    idx = np.argmax(mag[band])
    return float(freqs[band][idx])


def test_simulate_pump_returns_four_channels():
    """Le simulateur retourne les 4 canaux specifies (vibration, pressure, flow, temperature)."""
    signals = simulate_pump(seed=42, rpm=RPM_TEST)
    expected_channels = {"vibration", "pressure", "flow", "temperature"}
    assert set(signals) == expected_channels
    n_expected = int(DURATION_S * FS)
    for ch_name, arr in signals.items():
        assert arr.shape == (n_expected,)
        assert np.all(np.isfinite(arr)), f"Canal {ch_name} contient NaN ou inf"


def test_simulate_pump_reproducible_with_same_seed():
    """Reproductibilite par seed (cf. doc architecture §7)."""
    s1 = simulate_pump(seed=2026, rpm=RPM_TEST)
    s2 = simulate_pump(seed=2026, rpm=RPM_TEST)
    for key in s1:
        np.testing.assert_array_equal(s1[key], s2[key])


def test_vibration_rms_in_healthy_range():
    """V2 : RMS vibration d'une pompe saine dans la plage 0.1-5 g.

    La spec brief mission dit 0.1-5 g sain. C'est une plage tres large
    (elle inclut ISO 10816 zone A et B). On utilise 0.05-2 g sain pour
    un modele N2 deterministe (un peu moins que la limite haute ISO zone B
    pour eviter les false negatives dues a un bruit de fond trop fort).
    """
    signals = simulate_pump(seed=0, rpm=RPM_TEST)
    summary = pump_diagnostic_summary(signals, FS)
    rms_g = summary["vibration_rms_g"]
    assert 0.05 < rms_g < 2.0, f"RMS sain hors plage : {rms_g:.3f} g"


def test_bpfo_peak_at_3000_rpm():
    """V1 : avec un defaut BPFO active, on observe un pic a la BPFO du 6206 a 3000 rpm.

    Geometrie 6206 : n=9, d=9.525 mm, D=34.55 mm, contact=0 deg.
    A 3000 rpm, fr=50 Hz, BPFO = 4.5 * 50 * (1 - 9.525/34.55) ~ 162.97 Hz.
    Tolerance ±2 bins FFT (0.5 Hz) pour absorber la discretisation.
    """
    signals = simulate_pump(
        seed=0,
        rpm=RPM_TEST,
        defect_config={"bearing_outer_severity": 1.0},
    )
    freqs, mag = _rfft(signals["vibration"], FS)

    fr_hz = rotational_frequency_hz(RPM_TEST)
    # BPFO du 6206 (geometrie catalogue SKF standard) :
    # (9/2) * 50 * (1 - 9.525/34.55) = 4.5 * 50 * 0.7243 = 162.97 Hz
    bpfo_expected = bpfo(9, fr_hz, 9.525, 34.55, 0.0)

    df = FS / len(signals["vibration"])
    f_tolerance = 2 * df  # ±2 bins = ±0.5 Hz

    found_freq = _peak_frequency(freqs, mag, bpfo_expected, f_half_width=2.0)
    assert abs(found_freq - bpfo_expected) <= f_tolerance, (
        f"Pic BPFO attendu a {bpfo_expected:.2f} Hz ±{f_tolerance:.2f} Hz, "
        f"trouve a {found_freq:.3f} Hz"
    )

    # Le pic BPFO doit etre significativement au-dessus du plancher de bruit
    peak_amp = _peak_in_band(freqs, mag, bpfo_expected, f_half_width=2.0)
    # Plancher de bruit loin de BPFO (bande 1-2 kHz, loin de BPFO et des
    # premiers harmoniques 1x/2x/3x).
    noise_band = (freqs >= 1000.0) & (freqs <= 2000.0)
    noise_floor = float(np.median(mag[noise_band]))
    assert peak_amp > 3 * noise_floor, (
        f"Rapport signal/bruit insuffisant : pic BPFO = {peak_amp:.4f} g, "
        f"plancher = {noise_floor:.4f} g"
    )


def test_cavitation_adds_energy_in_5_15khz_band():
    """La cavitation (defaut specifique pompe) ajoute de l'energie dans la bande 5-15 kHz.

    Cf. `docs/architecture_usine_simulation.md` §5.2 : signature cavitation
    = "large_bande_5_15kHz". C'est cette signature qui distingue la pompe
    d'un moteur ou d'un reducteur.
    """
    s_sain = simulate_pump(seed=0, rpm=RPM_TEST, defect_config={"cavitation_severity": 0.0})
    s_cavit = simulate_pump(
        seed=0, rpm=RPM_TEST, defect_config={"cavitation_severity": 1.0}
    )

    freqs_s, mag_s = _rfft(s_sain["vibration"], FS)
    freqs_c, mag_c = _rfft(s_cavit["vibration"], FS)

    cav_low, cav_high = CAVITATION_BAND_HZ
    band = (freqs_s >= cav_low) & (freqs_s <= cav_high)
    e_sain = float(np.sum(mag_s[band] ** 2))
    e_cavit = float(np.sum(mag_c[band] ** 2))

    # Avec cavitation severe, l'energie dans la bande 5-15 kHz doit
    # augmenter significativement (au moins 5x).
    assert e_cavit > 5 * e_sain, (
        f"Cavitation n'a pas assez augmente l'energie 5-15 kHz. "
        f"Sain = {e_sain:.4f}, cavitation = {e_cavit:.4f}"
    )


def test_pressure_mean_close_to_rated():
    """La pression moyenne est proche de la pression nominale (sanity check)."""
    rated_p = 4.0  # bar
    signals = simulate_pump(seed=0, rpm=RPM_TEST, rated_pressure_bar=rated_p)
    p_mean = float(np.mean(signals["pressure"]))
    # Tolerance ±20% (acceptable pour un signal N2 avec ondulation + bruit)
    assert abs(p_mean - rated_p) / rated_p < 0.20, (
        f"Pression moyenne {p_mean:.2f} bar trop eloignee du nominal {rated_p} bar"
    )


def test_seal_wear_reduces_pressure_and_flow():
    """L'usure garniture fait chuter la pression ET le debit (fuite interne)."""
    s_sain = simulate_pump(seed=0, rpm=RPM_TEST, defect_config={"seal_wear_severity": 0.0})
    s_usure = simulate_pump(
        seed=0, rpm=RPM_TEST, defect_config={"seal_wear_severity": 1.0}
    )
    assert float(np.mean(s_usure["pressure"])) < float(np.mean(s_sain["pressure"]))
    assert float(np.mean(s_usure["flow"])) < float(np.mean(s_sain["flow"]))


def test_simulate_pump_raises_on_unknown_bearing():
    """Geometrie inconnue -> erreur explicite (pas de mock silencieux, regle 0 mock)."""
    with pytest.raises(KeyError, match="Roulement 'INEXISTANT' absent"):
        simulate_pump(seed=0, rpm=RPM_TEST, bearing_key="INEXISTANT")
