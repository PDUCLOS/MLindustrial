"""Tests du modele N2 d'un reducteur helicoidal 2 etages.

Cible CDC §7.1 A3 : "les modeles physiques ont leurs raies - Spectre contient
frequences caracteristiques (BPFO, GMF, 1xfr)".

Cible mission : FFT contient un pic a GMF@input_rpm +/- 2 bins, et les defauts
generent des sidebands.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gearbox.helical import (
    HelicalDefectConfig,
    HelicalGearGeometry,
    compute_helical_gearbox_state,
    compute_fft,
    find_peak_bin,
    simulate_helical_gearbox,
)


# Configuration partagee par les tests
GEOM = HelicalGearGeometry()  # 20-60 x 20-60, ratio total 9:1
FS = 64000
DURATION = 4.0


def test_two_stage_reduction_ratios():
    """Le rapport de reduction total est (Z2/Z1) * (Z4/Z3) = 9 avec la geometrie par defaut."""
    geom = HelicalGearGeometry()
    assert geom.reduction_ratio == pytest.approx(9.0)


def test_gearbox_kinematics():
    """fr_intermediate = fr_input * (Z1/Z2) et fr_output = fr_intermediate * (Z3/Z4).

    Pour input_rpm=1500, Z1=Z3=20, Z2=Z4=60 :
        - fr_input = 25 Hz
        - fr_intermediate = 25 * 20/60 = 8.333... Hz
        - fr_output = 8.333... * 20/60 = 2.777... Hz
    """
    state = compute_helical_gearbox_state(GEOM, input_rpm=1500)
    assert state.fr_input_hz == pytest.approx(25.0)
    assert state.fr_intermediate_hz == pytest.approx(25.0 * 20 / 60)
    assert state.fr_output_hz == pytest.approx(25.0 * 20 / 60 * 20 / 60)
    # GMF invariance : Z1 * fr_input = Z2 * fr_intermediate
    assert state.gmf1_hz == pytest.approx(20 * 25.0)
    assert state.gmf1_hz == pytest.approx(60 * state.fr_intermediate_hz)
    # Meme chose pour etage 2
    assert state.gmf2_hz == pytest.approx(20 * state.fr_intermediate_hz)
    assert state.gmf2_hz == pytest.approx(60 * state.fr_output_hz)


def test_helical_gmf_peak_in_fft_within_2_bins():
    """Le spectre de la vibration doit contenir un pic a GMF1 +/- 2 bins FFT.

    64 kHz / 256000 echantillons = 0.25 Hz/bin, 2 bins = 0.5 Hz de tolerance.
    """
    output = simulate_helical_gearbox(
        seed=42, input_rpm=1500, gear_geometry=GEOM,
        duration_s=DURATION, fs=FS,
    )
    freqs, amplitude = compute_fft(output["vibration"], FS)
    state = compute_helical_gearbox_state(GEOM, input_rpm=1500)

    target_bin = int(round(state.gmf1_hz / (FS / len(output["vibration"]))))
    # On cherche le max dans une fenetre de +/- 5 bins pour la robustesse
    window = slice(max(0, target_bin - 5), target_bin + 6)
    peak_bin_local = int(np.argmax(amplitude[window]))
    peak_bin = window.start + peak_bin_local
    # Verifier la tolerance de +/- 2 bins
    assert abs(peak_bin - target_bin) <= 2, (
        f"Pic GMF1 a bin {peak_bin} ({freqs[peak_bin]:.2f} Hz), "
        f"attendu bin {target_bin} ({state.gmf1_hz:.2f} Hz), "
        f"ecart = {abs(peak_bin - target_bin)} bins."
    )
    # Le pic doit etre significativement au-dessus du plancher de bruit
    noise_floor = float(np.median(amplitude))
    assert amplitude[peak_bin] > 5.0 * noise_floor, (
        f"Pic GMF1 a {amplitude[peak_bin]:.4f} g, plancher median = {noise_floor:.4f} g. "
        f"Rapport signal/bruit insuffisant ({amplitude[peak_bin]/max(noise_floor, 1e-12):.2f})."
    )


def test_broken_tooth_produces_sidebands_around_gmf():
    """Une dent cassee doit produire un pic a fr_input (frequence de modulation)
    ET des sidebands nets a GMF +/- fr_input (signature classique engrenage).

    On verifie deux choses :
    1. Le pic a fr_input (la frequence de modulation) est au moins 2x plus
       fort dans le signal defectueux que dans le sain.
    2. Au moins une des deux sidebands (GMF +/- fr_input) est plus forte
       dans le signal defectueux.
    """
    state = compute_helical_gearbox_state(GEOM, input_rpm=1500)
    fr_input = state.fr_input_hz
    n = int(FS * DURATION)
    bin_res = FS / n  # 0.25 Hz/bin

    # Signal de reference (sain)
    healthy = simulate_helical_gearbox(
        seed=42, input_rpm=1500, gear_geometry=GEOM,
        defect_config=HelicalDefectConfig(),
        duration_s=DURATION, fs=FS,
    )
    # Signal avec dent cassee etage 1, dent #0
    broken = simulate_helical_gearbox(
        seed=42, input_rpm=1500, gear_geometry=GEOM,
        defect_config=HelicalDefectConfig(
            enable_broken_tooth=True, broken_tooth_stage=1, broken_tooth_index=0,
        ),
        duration_s=DURATION, fs=FS,
    )

    freqs_h, amp_h = compute_fft(healthy["vibration"], FS)
    freqs_b, amp_b = compute_fft(broken["vibration"], FS)

    def peak_at(spectrum, freqs, target_hz, tolerance_bins=3):
        bin_idx = int(round(target_hz / bin_res))
        lo = max(0, bin_idx - tolerance_bins)
        hi = min(len(spectrum), bin_idx + tolerance_bins + 1)
        return float(np.max(np.abs(spectrum[lo:hi])))

    # 1. Pic a fr_input (la modulation de la dent cassee)
    amp_fr_h = peak_at(amp_h, freqs_h, fr_input)
    amp_fr_b = peak_at(amp_b, freqs_b, fr_input)
    assert amp_fr_b > 2.0 * amp_fr_h, (
        f"Dent cassee : pic a fr_input={fr_input:.2f} Hz "
        f"defectueux {amp_fr_b:.5f} <= 2x sain {amp_fr_h:.5f}. "
        f"Pas de modulation visible."
    )

    # 2. Au moins une sideband a GMF +/- fr_input est plus forte
    amp_sb_lo_h = peak_at(amp_h, freqs_h, state.gmf1_hz - fr_input)
    amp_sb_lo_b = peak_at(amp_b, freqs_b, state.gmf1_hz - fr_input)
    amp_sb_hi_h = peak_at(amp_h, freqs_h, state.gmf1_hz + fr_input)
    amp_sb_hi_b = peak_at(amp_b, freqs_b, state.gmf1_hz + fr_input)
    assert (amp_sb_lo_b > amp_sb_lo_h) or (amp_sb_hi_b > amp_sb_hi_h), (
        f"Dent cassee : aucune sideband GMF+/-fr_input plus forte. "
        f"GMF-fr : sain={amp_sb_lo_h:.5f} vs bris={amp_sb_lo_b:.5f}, "
        f"GMF+fr : sain={amp_sb_hi_h:.5f} vs bris={amp_sb_hi_b:.5f}."
    )


def test_wear_increases_low_frequency_energy():
    """L'usure ajoute du bruit large bande (cf. architecture §6.3) -> energie
    accrue sur les basses frequences (envelope de modulation)."""
    healthy = simulate_helical_gearbox(
        seed=7, input_rpm=1500, gear_geometry=GEOM,
        defect_config=HelicalDefectConfig(),
        duration_s=DURATION, fs=FS,
    )
    worn = simulate_helical_gearbox(
        seed=7, input_rpm=1500, gear_geometry=GEOM,
        defect_config=HelicalDefectConfig(enable_wear=True, wear_severity=0.8),
        duration_s=DURATION, fs=FS,
    )
    # Le RMS total doit etre plus eleve avec usure severe
    assert np.std(worn["vibration"]) > np.std(healthy["vibration"])


def test_current_signal_contains_mains_50hz():
    """Le courant doit contenir la fondamentale secteur 50 Hz (MCSA, see
    theorie_reference.md §4)."""
    output = simulate_helical_gearbox(
        seed=1, input_rpm=1500, gear_geometry=GEOM,
        duration_s=DURATION, fs=FS,
    )
    freqs, amplitude = compute_fft(output["current"], FS)
    bin_50 = int(round(50.0 / (FS / len(output["current"]))))
    window = slice(max(0, bin_50 - 2), bin_50 + 3)
    peak_bin = window.start + int(np.argmax(amplitude[window]))
    assert abs(peak_bin - bin_50) <= 2, (
        f"Pas de pic a 50 Hz dans le courant (pic a {freqs[peak_bin]:.2f} Hz)."
    )
    # Amplitude pic a 50 Hz doit etre ~10 A (nominal), dans une fourchette
    assert amplitude[peak_bin] > 5.0, (
        f"Amplitude fondamentale 50 Hz = {amplitude[peak_bin]:.2f} A, attendu ~10 A nominal."
    )


def test_seed_determinism():
    """Deux appels avec la meme seed doivent retourner le meme signal."""
    out1 = simulate_helical_gearbox(
        seed=99, input_rpm=1500, gear_geometry=GEOM, duration_s=DURATION, fs=FS,
    )
    out2 = simulate_helical_gearbox(
        seed=99, input_rpm=1500, gear_geometry=GEOM, duration_s=DURATION, fs=FS,
    )
    np.testing.assert_array_equal(out1["vibration"], out2["vibration"])
    np.testing.assert_array_equal(out1["current"], out2["current"])


def test_invalid_input_rejected():
    """Garde-fous : rpm <= 0, helix_angle hors plage, dents <= 0."""
    with pytest.raises(ValueError):
        HelicalGearGeometry(z1=0)
    with pytest.raises(ValueError):
        HelicalGearGeometry(helix_angle_deg=60.0)
    with pytest.raises(ValueError):
        compute_helical_gearbox_state(GEOM, input_rpm=0)
    with pytest.raises(ValueError):
        simulate_helical_gearbox(seed=0, input_rpm=1500, gear_geometry=GEOM, duration_s=-1.0)


def test_find_peak_bin_helper():
    """Le helper `find_peak_bin` retrouve un pic injecte au milieu d'un fond bruite."""
    fs = 1000.0
    n = 4000
    t = np.arange(n) / fs
    sig = 0.1 * np.random.default_rng(0).standard_normal(n)
    sig += 2.0 * np.cos(2.0 * np.pi * 123.4 * t)
    freqs, amp = compute_fft(sig, int(fs))
    bin_idx = find_peak_bin(amp, freqs, 123.4, tolerance_bins=3)
    assert bin_idx is not None
    assert abs(freqs[bin_idx] - 123.4) < 5.0  # fenetre etroite autour de 123.4 Hz
