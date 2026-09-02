"""Tests de la propagation P3 (harmoniques secteur via bus electrique partage).

Cible CDC §7.1 A5 : "Propagation P3 electrique - VFD M1 -> harmoniques 50 Hz
visibles sur M2-M5".

Modele : Vh/Vh_nominal = 1 / (1 + (Zbus/Zcharge) * h^2).
La verification : un signal source avec un pic H3 (150 Hz) genere un signal
cible avec un pic H3 visible (attenue, mais au-dessus du plancher de bruit).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.propagation.electrical import (
    MAINS_HZ,
    VFD_HARMONIC_RANKS,
    ElectricalBusCoupling,
    ElectricalPropagator,
)

FS = 64000
DURATION = 1.0  # 1 s : fenetre suffisante pour 50 Hz (20 periodes entieres)


def _current_with_harmonics(
    mains_amp: float,
    h3_amp: float,
    fs: int = FS,
    duration: float = DURATION,
) -> np.ndarray:
    """Cree un signal courant contenant la fondamentale 50 Hz et une harmonique H3 (150 Hz)."""
    n = int(round(fs * duration))
    t = np.arange(n) / fs
    return (
        mains_amp * np.sin(2.0 * np.pi * MAINS_HZ * t)
        + h3_amp * np.sin(2.0 * np.pi * 3.0 * MAINS_HZ * t)
    )


def _peak_at(signal: np.ndarray, f0: float, fs: int, tolerance_bins: int = 5) -> float:
    """Mesure l'amplitude du pic a f0 (methode Hann, normalisee en amplitude pic)."""
    n = len(signal)
    window = np.hanning(n)
    spectrum = np.fft.rfft(signal * window)
    target_bin = int(round(f0 / (fs / n)))
    lo = max(0, target_bin - tolerance_bins)
    hi = min(len(spectrum), target_bin + tolerance_bins + 1)
    return 2.0 * float(np.max(np.abs(spectrum[lo:hi]))) / n


def test_electrical_h3_visible_on_target():
    """H3 (150 Hz) generee par M1 doit etre visible (attenuee) sur le courant de M2."""
    mains_amp = 10.0
    h3_amp = 0.4  # 4% de la fondamentale, typique d'un VFD 6 pulses (inferred)
    # Couplage par defaut : Zbus/Zcharge = 0.1
    coupling = ElectricalBusCoupling(zbus_over_zcharge=0.1)
    propagator = ElectricalPropagator(
        fs=FS, default_coupling=coupling, harmonic_ranks=VFD_HARMONIC_RANKS,
    )
    source_signal = _current_with_harmonics(mains_amp=mains_amp, h3_amp=h3_amp)
    result = propagator.propagate(
        signal_dict={"current": source_signal},
        source_machine="M1",
        target_machines=["M2"],
        couplings={"M2": coupling},
    )
    target_signal = result["M2"]["current"]
    src_h3 = _peak_at(source_signal, 3.0 * MAINS_HZ, FS)
    tgt_h3 = _peak_at(target_signal, 3.0 * MAINS_HZ, FS)

    # 1. Le pic H3 doit etre visible au-dessus du plancher de bruit spectral.
    #    On evalue le plancher dans une bande eloignee des harmoniques secteur
    #    (5-6 kHz : pas d'harmonique VFD dans cette zone pour le modele).
    n = len(target_signal)
    window = np.hanning(n)
    spectrum = np.fft.rfft(target_signal * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    noise_mask = (freqs >= 5000.0) & (freqs <= 6000.0)
    noise_floor = float(np.median(np.abs(spectrum[noise_mask])))
    assert tgt_h3 > 5.0 * noise_floor, (
        f"H3 invisible sur M2 (amplitude {tgt_h3:.5f}, plancher {noise_floor:.5f})."
    )
    # 2. L'attenuation doit etre conforme a la formule (1 + 0.1 * 9 = 1.9,
    #    facteur 0.526, ~ -5.6 dB).
    analytical_factor = 1.0 / (1.0 + 0.1 * 9)
    measured_factor = tgt_h3 / src_h3
    assert abs(measured_factor - analytical_factor) < 0.05, (
        f"Facteur d'attenuation H3 : {measured_factor:.3f} (mesure) vs "
        f"{analytical_factor:.3f} (theorie). Ecart trop grand."
    )


def test_electrical_higher_rank_more_attenuated():
    """Les rangs superieurs (H5, H7) sont plus attenues que H3 pour un meme
    rapport d'impedance (formule en h^2)."""
    coupling = ElectricalBusCoupling(zbus_over_zcharge=0.1)
    propagator = ElectricalPropagator(
        fs=FS, default_coupling=coupling, harmonic_ranks=VFD_HARMONIC_RANKS,
    )
    att_h3 = propagator.attenuation_db(3, coupling)
    att_h5 = propagator.attenuation_db(5, coupling)
    att_h7 = propagator.attenuation_db(7, coupling)
    assert att_h5 > att_h3, f"H5 ({att_h5:.2f} dB) devrait etre plus attenuee que H3 ({att_h3:.2f} dB)."
    assert att_h7 > att_h5
    # Verification de la formule : att = 20*log10(1 + z*h^2)
    # H5 / H3 en dB : 20*log10((1 + 0.1*25)/(1 + 0.1*9)) = 20*log10(3.5/1.9)
    expected_diff = 20.0 * np.log10((1.0 + 0.1 * 25) / (1.0 + 0.1 * 9))
    assert abs((att_h5 - att_h3) - expected_diff) < 0.01


def test_electrical_attenuation_increases_with_zbus_over_zcharge():
    """Plus le rapport Zbus/Zcharge est grand (bus plus "faible"), plus l'attenuation
    d'une harmonique donnee est elevee."""
    propagator = ElectricalPropagator(fs=FS, harmonic_ranks=VFD_HARMONIC_RANKS)
    att_low = propagator.attenuation_db(5, ElectricalBusCoupling(zbus_over_zcharge=0.01))
    att_mid = propagator.attenuation_db(5, ElectricalBusCoupling(zbus_over_zcharge=0.1))
    att_high = propagator.attenuation_db(5, ElectricalBusCoupling(zbus_over_zcharge=1.0))
    assert att_low < att_mid < att_high


def test_electrical_no_current_signal_returns_zeros():
    """Si le signal source n'a pas de canal `current`, le resultat est un dict vide
    par cible (pas d'erreur)."""
    propagator = ElectricalPropagator(fs=FS)
    result = propagator.propagate(
        signal_dict={"vibration": np.zeros(FS)},  # pas de 'current'
        source_machine="M1",
        target_machines=["M2"],
    )
    assert "M2" in result
    # Le canal 'vibration' n'est pas du ressort de la propagation electrique
    # -> le propagateur met 'current' (absent) et laisse les autres canaux
    # comme zeros explicites pour signaler "non propage".
    assert "current" not in result["M2"]
    assert np.all(result["M2"]["vibration"] == 0.0)


def test_electrical_no_self_propagation_to_source():
    """Le propagateur ne propage PAS vers la machine source elle-meme.

    Le bridge filtre les auto-propagations, mais on verifie ici qu'un appel
    direct avec la source dans les cibles ne corrompt pas le resultat des
    autres cibles.
    """
    source_signal = _current_with_harmonics(mains_amp=10.0, h3_amp=0.4)
    propagator = ElectricalPropagator(fs=FS, harmonic_ranks=VFD_HARMONIC_RANKS)
    result = propagator.propagate(
        signal_dict={"current": source_signal},
        source_machine="M1",
        target_machines=["M1", "M2"],  # M1 dans les cibles par accident
    )
    # M2 doit avoir un signal non-trivial (le pic H3 a etc propage)
    assert _peak_at(result["M2"]["current"], 3.0 * MAINS_HZ, FS) > 0.0
