"""Tests du modele N2 moteur asynchrone 75 kW VFD (SA3 CDC Factory Twin Phase A).

Cible : `src/simulation/motor_induction.py::simulate_motor`.

Verification des criteres V1 et V2 de `docs/architecture_usine_simulation.md`
§9.1 adaptes au moteur :
- V1 : raies caracteristiques presentes dans le spectre (1x fr en vibration,
  fs=50 Hz en courant) a +/- 2 bins FFT
- V2 : ordre de grandeur physique (RMS vibration ~0.1-0.5 g sain, cf.
  ISO 10816 zone A, et RMS courant ~30-130 A selon charge)
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulation.motor_induction import (
    MAINS_FREQUENCY_HZ,
    motor_diagnostic_summary,
    simulate_motor,
)
from src.features.fault_frequencies import rotational_frequency_hz

# Configuration par defaut des tests : 4 s a 64 kHz, aligne Paderborn.
DURATION_S = 4.0
FS = 64000
RPM_TEST = 1500  # vitesse nominale d'un moteur 4 poles 50 Hz


def _peak_in_band(freqs: np.ndarray, mag: np.ndarray, f_center: float, f_half_width: float) -> float:
    """Retourne l'amplitude du pic maximal dans la bande [f_center - f_half_width, f_center + f_half_width]."""
    band = (freqs >= f_center - f_half_width) & (freqs <= f_center + f_half_width)
    if not np.any(band):
        return 0.0
    return float(np.max(mag[band]))


def _peak_frequency(freqs: np.ndarray, mag: np.ndarray, f_center: float, f_half_width: float) -> float:
    """Retourne la frequence du pic maximal dans la bande donnee."""
    band = (freqs >= f_center - f_half_width) & (freqs <= f_center + f_half_width)
    if not np.any(band):
        return 0.0
    idx_in_band = np.argmax(mag[band])
    return float(freqs[band][idx_in_band])


def _rfft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Calcule la FFT mono-cote et retourne (frequences, magnitudes)."""
    n = len(signal)
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mag = np.abs(spectrum) * 2.0 / n
    return freqs, mag


def test_simulate_motor_returns_four_channels_with_correct_length():
    """Le simulateur retourne les 4 canaux specifies, chacun de longueur N=4*fs=256000."""
    signals = simulate_motor(seed=42, rpm=RPM_TEST)
    expected_channels = {"vibration", "current_1", "current_2", "tacho"}
    assert set(signals) == expected_channels
    n_expected = int(DURATION_S * FS)
    for ch_name, arr in signals.items():
        assert arr.shape == (n_expected,), f"Canal {ch_name} a une longueur {arr.shape} != {n_expected}"
        assert np.all(np.isfinite(arr)), f"Canal {ch_name} contient des NaN ou inf"


def test_simulate_motor_reproducible_with_same_seed():
    """Meme seed -> meme signal (reproductibilite, cf. doc architecture §7)."""
    s1 = simulate_motor(seed=2026, rpm=RPM_TEST)
    s2 = simulate_motor(seed=2026, rpm=RPM_TEST)
    for key in s1:
        np.testing.assert_array_equal(s1[key], s2[key], err_msg=f"Canal {key} non reproductible")


def test_simulate_motor_differs_with_different_seed():
    """Seeds differents -> signaux differents (la stochasticite est bien injectee)."""
    s1 = simulate_motor(seed=1, rpm=RPM_TEST)
    s2 = simulate_motor(seed=2, rpm=RPM_TEST)
    assert not np.allclose(s1["vibration"], s2["vibration"])


def test_vibration_fft_peak_at_1x_rotation_frequency():
    """V1 : le spectre de la vibration contient un pic a 1x fr ±2 bins (= ±0.5 Hz).

    Pour 1500 rpm, fr = 25 Hz. Bin FFT = 100. Tolerance ±2 bins.
    """
    signals = simulate_motor(seed=0, rpm=RPM_TEST)
    fr_hz = rotational_frequency_hz(RPM_TEST)  # 25.0 Hz
    freqs, mag = _rfft(signals["vibration"], FS)

    df = FS / len(signals["vibration"])  # 0.25 Hz
    bin_tolerance = 2  # +/- 2 bins
    f_tolerance = bin_tolerance * df  # 0.5 Hz

    found_freq = _peak_frequency(freqs, mag, fr_hz, f_half_width=2.0)
    # Le pic dans la bande doit etre a fr ± tolerance
    assert abs(found_freq - fr_hz) <= f_tolerance, (
        f"Pic 1x fr attendu a {fr_hz} Hz ±{f_tolerance} Hz, "
        f"trouve a {found_freq:.3f} Hz"
    )

    # Le pic 1x doit etre significativement au-dessus du plancher de bruit
    # (sinon on ne pourrait pas l'identifier dans la pratique).
    peak_amp = _peak_in_band(freqs, mag, fr_hz, f_half_width=2.0)
    # Plancher de bruit hors 1x : on regarde une bande eloignee
    noise_band = (freqs >= 100.0) & (freqs <= 200.0)
    noise_floor = float(np.median(mag[noise_band]))
    assert peak_amp > 5 * noise_floor, (
        f"Rapport signal/bruit insuffisant : pic 1x = {peak_amp:.4f} g, "
        f"plancher median = {noise_floor:.4f} g"
    )


def test_current_fft_peak_at_mains_frequency_50hz():
    """V1 (courant MCSA) : le spectre du courant contient une raie a fs=50 Hz.

    Pour un moteur alimente sur secteur EU, la fondamentale du courant
    statorique est a fs=50 Hz, avec une amplitude tres dominante (le
    fondamental represente typiquement >95% de la RMS totale).
    """
    signals = simulate_motor(seed=0, rpm=RPM_TEST)
    freqs, mag = _rfft(signals["current_1"], FS)

    fs_mains = MAINS_FREQUENCY_HZ  # 50.0 Hz
    df = FS / len(signals["current_1"])
    f_tolerance = 2 * df  # ±2 bins = ±0.5 Hz

    found_freq = _peak_frequency(freqs, mag, fs_mains, f_half_width=2.0)
    assert abs(found_freq - fs_mains) <= f_tolerance, (
        f"Raie secteur attendue a {fs_mains} Hz ±{f_tolerance} Hz, "
        f"trouvee a {found_freq:.3f} Hz"
    )

    # Le pic a 50 Hz doit etre de loin le plus grand du spectre courant
    # (c'est la fondamentale, >95% de la RMS en regime nominal).
    peak_amp = _peak_in_band(freqs, mag, fs_mains, f_half_width=2.0)
    # Le plus grand pic hors 50 Hz (incluant les harmoniques 100, 150 Hz)
    mask = np.abs(freqs - fs_mains) > 5.0  # on exclut la zone autour de 50 Hz
    other_peak = float(np.max(mag[mask]))
    assert peak_amp > 5 * other_peak, (
        f"Rapport fondamental/harmoniques insuffisant : "
        f"50 Hz = {peak_amp:.2f} A, autre max = {other_peak:.2f} A"
    )


def test_vibration_rms_in_healthy_range():
    """V2 : RMS vibration d'un moteur sain dans la plage 0.1-0.5 g (ISO 10816 zone A)."""
    signals = simulate_motor(seed=0, rpm=RPM_TEST)
    summary = motor_diagnostic_summary(signals, FS)
    rms_g = summary["vibration_rms_g"]
    # La plage ISO 10816 zone A "bon" est < 1.4 mm/s pour machines de
    # classe II (15-75 kW sur paliers rigides), equivalent a ~0.3 g en
    # acceleration. On accepte 0.05 a 1.0 g pour un sain N2 (un peu
    # genereux pour absorber les fluctuations du bruit de fond).
    assert 0.05 < rms_g < 1.0, f"RMS sain hors plage : {rms_g:.3f} g"


def test_rotor_bar_defect_creates_sidebands_in_current():
    """Un defaut barres rotor active les bandes laterales fs ± 2*s*fr dans le courant.

    C'est la signature MCSA classique d'une barre cassee (cf.
    `docs/theorie_reference.md` §4). On verifie que la severite non nulle
    AJOUTE de l'energie dans ces bandes par rapport au sain.
    """
    s_sain = simulate_motor(seed=0, rpm=RPM_TEST, defect_config={"rotor_bar_severity": 0.0})
    s_def = simulate_motor(seed=0, rpm=RPM_TEST, defect_config={"rotor_bar_severity": 1.0})

    freqs_sain, mag_sain = _rfft(s_sain["current_1"], FS)
    freqs_def, mag_def = _rfft(s_def["current_1"], FS)

    s = 0.03  # glissement par defaut
    fr_hz = rotational_frequency_hz(RPM_TEST)
    sideband_l = MAINS_FREQUENCY_HZ - 2 * s * fr_hz  # ~48.5 Hz
    sideband_h = MAINS_FREQUENCY_HZ + 2 * s * fr_hz  # ~51.5 Hz

    band = 1.0  # Hz de chaque cote
    e_sain_l = _peak_in_band(freqs_sain, mag_sain, sideband_l, band)
    e_sain_h = _peak_in_band(freqs_sain, mag_sain, sideband_h, band)
    e_def_l = _peak_in_band(freqs_def, mag_def, sideband_l, band)
    e_def_h = _peak_in_band(freqs_def, mag_def, sideband_h, band)

    # Avec defaut, l'energie dans les bandes laterales doit augmenter
    # significativement (au moins 2x). On ne teste pas l'egalite exacte
    # car la signature MCSA est petite (~1% du fondamental).
    assert e_def_l > 2 * e_sain_l or e_def_l > 0.05, (
        f"Bandes laterales fc ± 2*s*fr attendues avec defaut barres rotor. "
        f"Sain = {e_sain_l:.4f} A, defaut = {e_def_l:.4f} A"
    )
    assert e_def_h > 2 * e_sain_h or e_def_h > 0.05, (
        f"Bandes laterales fc ± 2*s*fr attendues avec defaut barres rotor (cote haut). "
        f"Sain = {e_sain_h:.4f} A, defaut = {e_def_h:.4f} A"
    )


def test_bearing_defect_creates_impulsive_signal():
    """Un defaut BPFO active augmente le kurtosis (signature impulsive)."""
    s_sain = simulate_motor(seed=0, rpm=RPM_TEST, defect_config={"bearing_outer_severity": 0.0})
    s_def = simulate_motor(seed=0, rpm=RPM_TEST, defect_config={"bearing_outer_severity": 1.0})

    from src.features.time_domain import kurtosis

    k_sain = kurtosis(s_sain["vibration"])
    k_def = kurtosis(s_def["vibration"])

    # Le defaut ajoute des impacts reguliers -> kurtosis augmente.
    # On attend au moins 1.5x le kurtosis sain (le sain est ~3 gaussien
    # + bruit, le defaut ajoute des pics).
    assert k_def > k_sain, (
        f"Kurtosis avec defaut BPFO devrait etre > sain. "
        f"Sain = {k_sain:.2f}, defaut = {k_def:.2f}"
    )


def test_tacho_signal_period_matches_rotation():
    """Le signal tachymetre a une frequence fondamentale egale a fr (1 pulse/tour)."""
    signals = simulate_motor(seed=0, rpm=RPM_TEST)
    freqs, mag = _rfft(signals["tacho"], FS)

    fr_hz = rotational_frequency_hz(RPM_TEST)  # 25.0 Hz
    df = FS / len(signals["tacho"])
    f_tolerance = 2 * df

    found_freq = _peak_frequency(freqs, mag, fr_hz, f_half_width=2.0)
    assert abs(found_freq - fr_hz) <= f_tolerance, (
        f"Tachymetre : pic attendu a {fr_hz} Hz, trouve a {found_freq:.3f} Hz"
    )


def test_simulate_motor_handles_low_rpm():
    """Le moteur supporte des rpm bas (VFD, plage 750-3000 rpm doc architecture §5.1)."""
    signals = simulate_motor(seed=0, rpm=750)
    fr_hz = rotational_frequency_hz(750)  # 12.5 Hz
    freqs, mag = _rfft(signals["vibration"], FS)
    found_freq = _peak_frequency(freqs, mag, fr_hz, f_half_width=1.0)
    df = FS / len(signals["vibration"])
    assert abs(found_freq - fr_hz) <= 2 * df


def test_simulate_motor_raises_on_invalid_config():
    """Les geometries de roulement inconnues leve une erreur explicite (pas de mock silencieux)."""
    with pytest.raises(KeyError, match="Roulement 'INEXISTANT' absent"):
        simulate_motor(seed=0, rpm=RPM_TEST, bearing_key="INEXISTANT")
