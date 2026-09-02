"""Tests du modele N2 presse mecanique 100T a 60 cycles/min (SA5 CDC Factory Twin Phase A).

Cible : `src/simulation/press_mechanical.py::simulate_press`.

Verification des criteres V1 et V2 de `docs/architecture_usine_simulation.md`
§9.1 adaptes a la presse :
- V1 : impacts cycliques visibles (autocorrelation pic a la periode de
  cycle) et raies rotation bielle (1x, 2x fr) presentes dans le spectre
- V2 : RMS vibration compatible avec les impacts d'embrayage et de frappe
  (RMS eleve en N2 a cause des pics, > 0.5 g meme en sain)
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.fault_frequencies import rotational_frequency_hz
from src.simulation.press_mechanical import (
    DEFAULT_CRANKSHAFT_RPM,
    simulate_press,
)

DURATION_S = 4.0
FS = 64000
CYCLE_FREQ_HZ = 1.0  # 60 cycles/min
CYCLE_PERIOD_S = 1.0 / CYCLE_FREQ_HZ  # 1.0 s


def _rfft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
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


def test_simulate_press_returns_two_channels():
    """Le simulateur retourne 'vibration' et 'current' (spec M6)."""
    signals = simulate_press(seed=42)
    expected_channels = {"vibration", "current"}
    assert set(signals) == expected_channels
    n_expected = int(DURATION_S * FS)
    for ch_name, arr in signals.items():
        assert arr.shape == (n_expected,)
        assert np.all(np.isfinite(arr)), f"Canal {ch_name} contient NaN ou inf"


def test_simulate_press_reproducible_with_same_seed():
    s1 = simulate_press(seed=2026)
    s2 = simulate_press(seed=2026)
    for key in s1:
        np.testing.assert_array_equal(s1[key], s2[key])


def test_cyclic_impacts_visible_in_autocorrelation():
    """Les impacts cycliques (embrayage + frappe) produisent un pic d'autocorrelation a T_cycle.

    A 60 cycles/min, T_cycle = 1.0 s. L'autocorrelation du signal de
    vibration doit avoir un pic significatif a lag = fs (= 64000 samples
    pour fs=64 kHz et cycle 1s). Le pic doit etre superieur a la mediane
    de l'autocorrelation (signature d'une periodicite reelle, pas du
    bruit blanc).
    """
    signals = simulate_press(seed=0, cycle_freq_hz=CYCLE_FREQ_HZ)
    vib = signals["vibration"]

    # Autocorrelation biaisee via FFT (efficace pour longs signaux).
    n = len(vib)
    fft = np.fft.rfft(vib)
    acf = np.fft.irfft(fft * np.conj(fft), n=n)
    # Normalisation par la valeur a lag=0 (variance du signal).
    acf_norm = acf / acf[0] if acf[0] > 0 else acf

    # Pic attendu a lag = cycle_period_s * fs samples.
    expected_lag = int(CYCLE_PERIOD_S * FS)
    tolerance_lag = int(0.05 * FS)  # ±50 ms (le jitter est de ±2% du cycle)
    band = slice(expected_lag - tolerance_lag, expected_lag + tolerance_lag)
    peak_at_cycle = float(np.max(acf_norm[band]))

    # Mediane de l'autocorrelation sur la fenetre 0.2-0.8 cycle (entre
    # 2 cycles consecutifs, hors du pic).
    other_lags = np.concatenate(
        [
            acf_norm[int(0.20 * FS) : int(0.45 * FS)],
            acf_norm[int(0.55 * FS) : int(0.80 * FS)],
        ]
    )
    median_other = float(np.median(other_lags))

    assert peak_at_cycle > 2 * max(median_other, 0.01), (
        f"Autocorrelation a T_cycle = {peak_at_cycle:.3f} (apres normalisation), "
        f"median hors pic = {median_other:.3f}. "
        f"Les impacts cycliques ne sont pas assez marques."
    )


def test_press_vibration_contains_1x_crankshaft_frequency():
    """V1 : la rotation de la bielle (200 rpm = 3.33 Hz) est visible dans le spectre."""
    signals = simulate_press(seed=0, crankshaft_rpm=DEFAULT_CRANKSHAFT_RPM)
    freqs, mag = _rfft(signals["vibration"], FS)

    fr_hz = rotational_frequency_hz(DEFAULT_CRANKSHAFT_RPM)  # ~3.33 Hz
    df = FS / len(signals["vibration"])
    f_tolerance = 2 * df  # ±2 bins (tres fin a 4s de signal)

    # 1x fr doit etre visible (balourd de la bielle)
    found_1x = _peak_frequency(freqs, mag, fr_hz, f_half_width=0.5)
    assert abs(found_1x - fr_hz) <= f_tolerance, (
        f"Pic 1x fr_bielle attendu a {fr_hz:.2f} Hz, trouve a {found_1x:.3f} Hz"
    )

    # 2x fr doit aussi etre visible (desalignement)
    found_2x = _peak_frequency(freqs, mag, 2 * fr_hz, f_half_width=1.0)
    assert abs(found_2x - 2 * fr_hz) <= f_tolerance, (
        f"Pic 2x fr_bielle attendu a {2 * fr_hz:.2f} Hz, trouve a {found_2x:.3f} Hz"
    )


def test_press_vibration_rms_higher_than_baseline_machine():
    """V2 : la RMS vibration d'une presse saine est plus elevee que celle d'un moteur
    a cause des pics d'embrayage et de frappe.

    Comparaison : la presse a 1 coup/sec avec des pics a 8 g, donc sa RMS
    sur 4 s est naitre plus elevee que celle d'un moteur asynchrone
    lineaire en rotation (cf. moteur sain ~0.1-0.3 g).
    """
    signals = simulate_press(seed=0)
    from src.features.time_domain import rms

    rms_g = rms(signals["vibration"])
    # Plage attendue pour une presse 100T : 1-5 g RMS avec impacts
    # (les impacts a 8 g toutes les secondes elevent la RMS).
    assert rms_g > 0.5, f"RMS presse trop faible : {rms_g:.3f} g (attendu > 0.5 g)"
    assert rms_g < 10.0, f"RMS presse trop elevee : {rms_g:.3f} g (attendu < 10 g)"


def test_current_has_engagement_and_strike_peaks():
    """Le courant moteur de la presse presente des pics a l'embrayage et a la frappe.

    Pour un cycle de 1 s : embrayage a 0.1 s et frappe a 0.55 s. Le
    courant doit etre localement superieur au regime nominal (60% du
    nominal) a ces 2 instants.
    """
    signals = simulate_press(seed=0, cycle_freq_hz=CYCLE_FREQ_HZ)
    cur = signals["current"]

    # Regime nominal : 0.6 * i_peak. Les pics ajoutent 1.9 et 2.9 fois
    # i_peak par-dessus (cf. simulate_press).
    # On cherche le max du courant dans la fenetre autour de 0.1 s du
    # premier cycle (zone d'embrayage).
    emb_window = slice(int(0.08 * FS), int(0.20 * FS))
    frappe_window = slice(int(0.50 * FS), int(0.65 * FS))
    nominal_window = slice(int(0.65 * FS), int(0.90 * FS))  # entre frappe et fin de cycle

    peak_emb = float(np.max(cur[emb_window]))
    peak_frappe = float(np.max(cur[frappe_window]))
    peak_nominal = float(np.max(cur[nominal_window]))

    assert peak_emb > peak_nominal, (
        f"Pic embrayage attendu > nominal. Embrayage = {peak_emb:.2f} A, "
        f"nominal = {peak_nominal:.2f} A"
    )
    assert peak_frappe > peak_emb, (
        f"Pic frappe attendu > embrayage. Frappe = {peak_frappe:.2f} A, "
        f"embrayage = {peak_emb:.2f} A"
    )


def test_simulate_press_handles_multiple_cycles():
    """Le simulateur gere correctement un nombre explicite de cycles."""
    signals_default = simulate_press(seed=0)
    signals_explicit = simulate_press(seed=0, cycle_count=4)
    # Avec le meme seed, les 2 appels doivent etre identiques si le
    # nombre de cycles est le meme (4 cycles dans 4 s a 1 Hz).
    for key in signals_default:
        np.testing.assert_array_equal(signals_default[key], signals_explicit[key])


def test_simulate_press_raises_on_zero_cycles():
    """Cycle count = 0 leve une erreur explicite (pas de mock silencieux)."""
    with pytest.raises(ValueError, match="cycle_count doit etre"):
        simulate_press(seed=0, cycle_count=0)


def test_simulate_press_raises_on_unknown_bearing():
    with pytest.raises(KeyError, match="Roulement"):
        simulate_press(seed=0, bearing_keys=("INEXISTANT", "22220"))
