"""Helpers partages entre les simulateurs de la Phase A Factory Twin.

Tous les simulateurs (moteur, pompe, presse) ont besoin de :
- generer du bruit colore 1/f^alpha reproductible
- lire la geometrie d'un roulement depuis `configs/bearing_geometry.yaml`
- definir un dictionnaire de defauts par defaut (tous a 0 = sain)
- generer un signal tachymetre (1 pulse par tour)

Ces fonctions sont PRIVATISEES dans le module (`_helpers`) mais exposees
via `src/simulation/__init__.py` pour les tests et autres simulateurs
futurs (M3 ventilateur, M4 compresseur, etc. - voir
`docs/architecture_usine_simulation.md` §3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Chemin absolu vers la racine du projet (repose sur la structure du repo,
# pas sur cwd - plus robuste pour pytest qui peut etre lance de partout).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BEARING_GEOMETRY_PATH = _PROJECT_ROOT / "configs" / "bearing_geometry.yaml"


def bearing_geometry_from_yaml(bearing_key: str) -> dict[str, Any]:
    """Lit la geometrie d'un roulement depuis `configs/bearing_geometry.yaml`.

    Parameters
    ----------
    bearing_key : str
        Cle YAML (ex. "6203", "6206", "22320"). Doit exister dans
        `bearing_geometry.yaml::geometries`.

    Returns
    -------
    dict
        Sous-dictionnaire YAML (n_balls, ball_diameter_mm, pitch_diameter_mm,
        contact_angle_deg, etc.). Le champ `bearing_type` (optionnel,
        "spherical_roller" / "tapered_roller") est preserve quand present.

    Raises
    ------
    KeyError
        Si la cle n'existe pas dans le YAML. Pas de fallback silencieux :
        preferer une erreur explicite qu'un calcul sur une geometrie
        par defaut qui pourrait invalider la signature spectrale generee
        (cf. regle "0 mock", `docs/audit_zero_mock_2026-09-01.md` §3.3).
    """
    with _BEARING_GEOMETRY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    geometries = data["geometries"]
    if bearing_key not in geometries:
        raise KeyError(
            f"Roulement '{bearing_key}' absent de { _BEARING_GEOMETRY_PATH.name }. "
            f"Cles disponibles : {sorted(geometries)}"
        )
    return dict(geometries[bearing_key])


def default_defect_config() -> dict[str, float]:
    """Dictionnaire de defauts neutres (tout a 0 = machine saine).

    Toutes les severites sont 0.0 par defaut, ce qui produit un signal
    "sain de reference" pour la comparaison defaut/sain. Les cles sont
    figees pour eviter qu'un defaut oublie ne soit pas zero-e par defaut
    (cf. `docs/architecture_usine_simulation.md` §9.1 - tout defaut
    non-zero doit etre EXPLICITEMENT active par l'appelant).
    """
    return {
        # Spectre general
        "unbalance_severity": 0.0,        # 0-1, balourd (1x fr)
        "misalignment_severity": 0.0,     # 0-1, desalignement (1x + 2x fr)
        "eccentricity_severity": 0.0,     # 0-1, excentricite (moteur asynchrone)
        # Roulements (BPFO/BPFI/BSF/FTF)
        "bearing_outer_severity": 0.0,    # 0-1, defaut bague exterieure
        "bearing_inner_severity": 0.0,    # 0-1, defaut bague interieure
        "bearing_roller_severity": 0.0,   # 0-1, defaut bille/rouleau
        "bearing_cage_severity": 0.0,     # 0-1, defaut cage
        # Specifiques machines
        "rotor_bar_severity": 0.0,        # 0-1, barres rotor cassees (moteur asynchrone)
        "cavitation_severity": 0.0,       # 0-1, cavitation (pompe centrifuge)
        "seal_wear_severity": 0.0,        # 0-1, usure garniture (pompe)
    }


def colored_noise(n_samples: int, alpha: float, rng: np.random.Generator) -> np.ndarray:
    """Genere un bruit colore 1/f^alpha par filtrage FFT d'un bruit blanc.

    Algorithme classique (cf. Kasdin 1995, "Discrete simulation of colored
    noise and stochastic processes and 1/f^alpha power law noise generation") :
    on multiplie la transformee de Fourier d'un bruit blanc par un filtre
    en amplitude 1/f^(alpha/2), ce qui donne une DSP en 1/f^alpha.

    Parameters
    ----------
    n_samples : int
        Nombre d'echantillons du signal de sortie.
    alpha : float
        Exposant de la loi de puissance (1.0 = rose, 2.0 = brown, etc.).
        Valeurs typiques atelier : 1.5 a 2.5
        (cf. `docs/architecture_usine_simulation.md` §4.2).
    rng : np.random.Generator
        Generateur aleatoire (reproductibilite via seed, cf.
        `docs/architecture_usine_simulation.md` §7 "Seed et reproductibilite").

    Returns
    -------
    np.ndarray
        Signal temporel de longueur `n_samples`, moyenne nulle, RMS unitaire
        apres normalisation (le caller applique son facteur d'amplitude en g).
    """
    if n_samples < 2:
        raise ValueError(f"n_samples doit etre >= 2, recu {n_samples}")
    if alpha < 0:
        raise ValueError(f"alpha doit etre >= 0, recu {alpha}")

    white = rng.standard_normal(n_samples)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n_samples)

    # Eviter la division par 0 sur la composante DC. On fixe la composante
    # DC a 0 directement (le bruit n'a pas de composante continue par
    # definition), et on preserve legerement la basse frequence pour eviter
    # un pic artificiel.
    if freqs[0] == 0.0:
        spectrum[0] = 0.0
        freqs[0] = freqs[1] if len(freqs) > 1 else 1.0

    # Filtre en amplitude 1/f^(alpha/2) -> DSP en 1/f^alpha
    filt = freqs ** (-alpha / 2.0)
    # Normalisation pour avoir un RMS unitaire en sortie
    filt = filt / np.sqrt(np.mean(filt**2))

    colored_spectrum = spectrum * filt
    return np.fft.irfft(colored_spectrum, n=n_samples)


def tacho_pulse_train(
    n_samples: int,
    fr_hz: float,
    fs: int,
    duty: float = 0.1,
) -> np.ndarray:
    """Genere un signal tachymetre (1 pulse par tour, signal carre 0/1).

    Parameters
    ----------
    n_samples : int
        Longueur du signal de sortie.
    fr_hz : float
        Frequence de rotation (Hz). Si <= 0, retourne un signal nul.
    fs : int
        Frequence d'echantillonnage (Hz).
    duty : float, optional
        Rapport cyclique du pulse dans la periode (defaut 0.1 = 10%).
        Vrai pour un capteur optique avec un index par tour.

    Returns
    -------
    np.ndarray
        Signal 0/1 de longueur `n_samples` aligne sur le format Paderborn
        (un canal "tacho" supplementaire en supplement de vibration/courant).
    """
    if fr_hz <= 0 or fs <= 0:
        return np.zeros(n_samples)
    period_samples = int(round(fs / fr_hz))
    if period_samples < 2:
        return np.zeros(n_samples)
    pulse_samples = max(1, int(round(period_samples * duty)))

    out = np.zeros(n_samples)
    for start in range(0, n_samples, period_samples):
        end = min(start + pulse_samples, n_samples)
        out[start:end] = 1.0
    return out


def bearing_impacts(
    n_samples: int,
    fs: int,
    fault_freq_hz: float,
    amplitude_g: float,
    decay_time_s: float = 0.003,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Train d'impulsions amorties a une frequence caracteristique de defaut.

    Modelise un defaut localise (BPFO/BPFI/BSF/FTF) : un impact a chaque
    passage de l'element roulant sur le defaut, reponse mecanique du
    roulement (resonance structurelle + amortissement) modulee par une
    enveloppe exponentielle decroissante.

    Parameters
    ----------
    n_samples : int
        Longueur du signal.
    fs : int
        Frequence d'echantillonnage (Hz).
    fault_freq_hz : float
        Frequence de repetition des impacts (Hz). Si <= 0, retourne 0.
    amplitude_g : float
        Amplitude crete de l'impact en g. La RMS du train depends du
        nombre d'impacts et de la duree de decay.
    decay_time_s : float, optional
        Constante de temps de la decroissance exponentielle (defaut 3 ms,
        ordre de grandeur resonance structurelle roulement).
    rng : np.random.Generator, optional
        Si fourni, ajoute un jitter temporel (~1% de la periode) pour eviter
        un spectre trop propre (cf. §4.1 N2 "signal trop propre" doc
        architecture_usine_simulation.md).

    Returns
    -------
    np.ndarray
        Signal vibratoire (g) de longueur `n_samples`.
    """
    if fault_freq_hz <= 0 or amplitude_g == 0:
        return np.zeros(n_samples)
    period_samples = int(round(fs / fault_freq_hz))
    if period_samples < 4:
        return np.zeros(n_samples)

    decay_samples = max(2, int(round(decay_time_s * fs)))
    template_len = min(decay_samples, n_samples)
    decay_t = np.arange(template_len) / fs
    envelope = np.exp(-decay_t / decay_time_s)
    template = amplitude_g * envelope * np.sin(2 * np.pi * 500.0 * decay_t)
    # Note : 500 Hz est une resonance structurelle representative d'un
    # palier asynchrone (Paderborn observe des resonances autour de 300-800 Hz
    # sur le banc, voir `docs/known_issues.md` "resonance structurelle"). Ce
    # n'est PAS la frequence de repetition (fault_freq_hz) qui est donnee
    # par BPFO/BPFI/BSF/FTF.

    out = np.zeros(n_samples)
    n_impacts = n_samples // period_samples
    for i in range(n_impacts):
        if rng is not None:
            jitter = int(rng.integers(-period_samples // 100, period_samples // 100 + 1))
        else:
            jitter = 0
        start = i * period_samples + jitter
        if start < 0 or start >= n_samples:
            continue
        end = min(start + template_len, n_samples)
        out[start:end] += template[: end - start]
    return out
