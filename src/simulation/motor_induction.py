"""Modele N2 d'un moteur asynchrone 75 kW pilote par variateur (VFD).

Cible : SA3 du CDC (`docs/CDC_projet.md` §6.1), machine M1 du Factory Twin
Phase A (cf. `docs/architecture_usine_simulation.md` §5.1 et tableau §3).

Le modele N2 (déterministe) genere simultanement :
- un signal d'acceleration vibratoire (g), canal "vibration" - aligne format
  Paderborn (4 s a 64 kHz, soit 256 000 points)
- 2 signaux de courant statorique (A), canaux "current_1" et "current_2"
  (modelisation biphasée simplifiée - phases A et B d'un triphase)
- un signal tachymetre (canal "tacho", signal carré 0/1 a la frequence fr)

Signature spectrale :
- vibration : 1x, 2x, 3x, 4x fr (rotation et harmoniques) + raies BPFO/BPFI/BSF/FTF
  du roulement selectionne (defaut 6203, geometrie Paderborn-compatible) + bande
  large de bruit colore 1/f^alpha (alpha=1.8 typique atelier)
- courant : fondamentale secteur fs=50 Hz (et harmoniques 3fs, 5fs, 7fs
  du VFD) + bandes laterales a fs ± 2*s*fr (signature barres rotor cassees
  cf. `docs/theorie_reference.md` §4 MCSA)

Upgrade N3 (stochastique) reserve a une session ulterieure : voir §6.2 de
`docs/architecture_usine_simulation.md` pour le pattern N3 moteur (fluctuation
tension, bruit de glissement, harmoniques aleatoires).

Parametres physiques et leur source :
- vitesse synchrone 1500 rpm a 50 Hz / 4 poles : norme IEC 60034-1
  (cite `docs/architecture_usine_simulation.md` tableau §10 ligne "Vitesse
  nominale 50 Hz", `confidence: confirmed`)
- glissement nominal 3% a charge nom : ordre de grandeur standard moteur
  asynchrone 75 kW, marque `inferred` (pas de doc constructeur pour ce
  moteur simulé précis)
- amplitudes 1x/2x/3x/4x et BPFO : `inferred`, derives de l'ordre de
  grandeur ISO 10816 zone A sain (0.1-0.5 g RMS)
- amplitudes courant : `inferred`, derivees du ratio MCSA signature/defaut
  typique 1/1000 (cf. `docs/architecture_usine_simulation.md` tableau §10
  ligne "Courant MCSA amplitude")
- bruit colore 1/f^1.8 : `inferred`, ordre de grandeur atelier (cf. §4.2
  du meme doc)
- resonance structurelle des impacts roulement fixee a 500 Hz (constante
  du helper) : `inferred`, ordre de grandeur resonance palier asynchrone
  (300-800 Hz sur Paderborn reel, `docs/known_issues.md`)
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.features.fault_frequencies import (
    bpfi,
    bpfo,
    bsf,
    ftf,
    rotational_frequency_hz,
)
from src.features.time_domain import rms
from src.simulation._helpers import (
    bearing_geometry_from_yaml,
    bearing_impacts,
    colored_noise,
    default_defect_config,
    tacho_pulse_train,
)

# Glissement nominal a charge nominale. 3% est l'ordre de grandeur standard
# pour un moteur asynchrone 75 kW 4 poles, marque `confidence: inferred`
# (cf. docstring module).
DEFAULT_SLIP_AT_RATED_LOAD: float = 0.03

# Courant nominal approxime d'un moteur 75 kW en 400 V tri (I = P / (U*sqrt(3)*cos(phi)*eta)
# approxime par 130 A). `confidence: inferred` (pas de doc constructeur specifique).
DEFAULT_RATED_CURRENT_A: float = 130.0

# Frequence secteur EU (50 Hz), source : IEC 60034-1 / NF C 51-200.
MAINS_FREQUENCY_HZ: float = 50.0

# Amplitude crete d'un defaut barres rotor (g) en vibration. Typiquement
# faible (les barres cassees modulent surtout le couple et donc le
# courant, pas directement la vibration mecanique). `confidence: inferred`.
ROTOR_BAR_VIBRATION_AMPLITUDE_G: float = 0.08

# Amplitudes des 4 premiers harmoniques de rotation en g (sain).
# Ordre de grandeur ISO 10816 zone A : < 0.5 g RMS sain, avec 1x dominant
# (balourd residuel unavoidable) et harmoniques 2x/3x/4x plus faibles.
# `confidence: inferred` (derive des seuils ISO 10816 / ISO 20816).
_BASE_HARMONIC_AMP_G: tuple[float, ...] = (0.15, 0.04, 0.02, 0.01)


def simulate_motor(
    seed: int,
    rpm: float,
    defect_config: dict[str, float] | None = None,
    duration_s: float = 4.0,
    fs: int = 64000,
    bearing_key: str = "6203",
    slip: float = DEFAULT_SLIP_AT_RATED_LOAD,
    rated_current_a: float = DEFAULT_RATED_CURRENT_A,
) -> dict[str, np.ndarray]:
    """Simule un moteur asynchrone VFD 75 kW (modele N2 deterministe).

    Parameters
    ----------
    seed : int
        Graine du generateur aleatoire (reproductibilite, cf.
        `docs/architecture_usine_simulation.md` §7).
    rpm : float
        Vitesse de rotation mecanique reelle (tr/min). Pour un 4 poles
        50 Hz, la plage utile est ~0-1800 tr/min avec glissement ; au-dela,
        le moteur est en survitesse (mode generateur).
    defect_config : dict[str, float] or None, optional
        Dictionnaire de severite (0-1) par defaut. Si None, equivalent a
        tous les defauts a 0 (sain). Voir `default_defect_config()` pour
        la liste des cles.
    duration_s : float, optional
        Duree du signal en secondes (defaut 4.0, aligne Paderborn).
    fs : int, optional
        Frequence d'echantillonnage (defaut 64000, aligne Paderborn).
    bearing_key : str, optional
        Cle YAML du roulement dans `configs/bearing_geometry.yaml`
        (defaut "6203", geometrie Paderborn-compatible).
    slip : float, optional
        Glissement nominal a la charge du simulateur (defaut 0.03).
        Utilise pour la signature barres rotor dans le courant.
    rated_current_a : float, optional
        Courant nominal du moteur (defaut 130 A, ordre de grandeur 75 kW).

    Returns
    -------
    dict[str, np.ndarray]
        Dictionnaire avec 4 canaux :
        - 'vibration' (g), 1D array de longueur int(duration_s * fs)
        - 'current_1' (A), phase A du courant statorique
        - 'current_2' (A), phase B (dephasage 120 deg) du courant statorique
        - 'tacho' (sans dimension 0/1), signal tachymetre
    """
    config = default_defect_config()
    if defect_config is not None:
        config.update(defect_config)

    geom = bearing_geometry_from_yaml(bearing_key)
    n_balls = int(geom["n_balls"])
    ball_d_mm = float(geom["ball_diameter_mm"])
    pitch_d_mm = float(geom["pitch_diameter_mm"])
    phi_deg = float(geom.get("contact_angle_deg", 0.0))

    n = int(round(duration_s * fs))
    if n < 2:
        raise ValueError(f"duration_s * fs doit donner >= 2 samples, recu {n}")
    t = np.arange(n) / fs
    rng = np.random.default_rng(seed)

    fr_hz = rotational_frequency_hz(rpm)
    fs_mains = MAINS_FREQUENCY_HZ

    # ------------------------------------------------------------------
    # CANAL VIBRATION (g)
    # ------------------------------------------------------------------
    vibration = np.zeros(n)

    # (1) Rotation de base : 1x, 2x, 3x, 4x fr (amplitudes decroissantes)
    # Les phases sont aleatoires pour eviter un signal trop propre (cf. §4.1
    # N2 "trop propre").
    for k, amp in enumerate(_BASE_HARMONIC_AMP_G, start=1):
        # 1x contient l'effet balourd ; les harmoniques sont plus faibles.
        # severity multiplicateur sur l'harmonique 1x pour activer un balourd
        if k == 1:
            effective_amp = amp * (1.0 + 4.0 * config["unbalance_severity"])
        else:
            effective_amp = amp
        vibration += effective_amp * np.sin(2 * np.pi * k * fr_hz * t + rng.uniform(0, 2 * np.pi))

    # (2) Excentricite (raie a fr additionnelle, superposee au 1x ci-dessus
    # avec un dephasage distinct). Effet purement mecanique pour un moteur
    # asynchrone : entrefer non uniforme -> attraction radiale.
    if config["eccentricity_severity"] > 0:
        vibration += (
            0.05
            * config["eccentricity_severity"]
            * np.sin(2 * np.pi * fr_hz * t + rng.uniform(0, 2 * np.pi))
        )

    # (3) Defauts roulement : BPFO (bague ext), BPFI (bague int), BSF (bille).
    # FTF (cage) ignore ici - frequence trop basse (<10 Hz pour le 6203) et
    # signature faible, pas discriminant en N2.
    bpfo_hz = bpfo(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)
    bpfi_hz = bpfi(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)
    bsf_hz = bsf(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)

    vibration += bearing_impacts(
        n, fs, bpfo_hz, amplitude_g=1.0 * config["bearing_outer_severity"], rng=rng
    )
    vibration += bearing_impacts(
        n, fs, bpfi_hz, amplitude_g=0.8 * config["bearing_inner_severity"], rng=rng
    )
    vibration += bearing_impacts(
        n, fs, bsf_hz, amplitude_g=0.4 * config["bearing_roller_severity"], rng=rng
    )

    # (4) Barres rotor cassees : effet le plus visible dans le courant (cf.
    # MCSA §4 theorie_reference), mais on injecte une legere modulation de
    # vitesse donc de vibration a 2*s*fr.
    if config["rotor_bar_severity"] > 0:
        vibration += (
            ROTOR_BAR_VIBRATION_AMPLITUDE_G
            * config["rotor_bar_severity"]
            * np.sin(2 * np.pi * 2 * slip * fr_hz * t)
        )

    # (5) Bruit colore de fond 1/f^1.8 (ordre de grandeur atelier).
    vibration += 0.02 * colored_noise(n, alpha=1.8, rng=rng)

    # ------------------------------------------------------------------
    # CANAUX COURANT (A) - phases A et B (modelisation biphasée simplifiée)
    # ------------------------------------------------------------------
    # Amplitudecrete phase = I_nom / sqrt(3) * sqrt(2) (relation triphase
    # equilibree). I_nom est la valeur RMS par phase.
    i_peak = rated_current_a * np.sqrt(2.0) / np.sqrt(3.0)

    current_1 = i_peak * np.sin(2 * np.pi * fs_mains * t)
    current_2 = i_peak * np.sin(2 * np.pi * fs_mains * t - 2 * np.pi / 3.0)

    # Harmoniques VFD : 3fs, 5fs, 7fs (amplitudes relatives typiques).
    for k_harm, rel_amp in [(3, 0.05), (5, 0.03), (7, 0.02)]:
        current_1 += i_peak * rel_amp * np.sin(2 * np.pi * k_harm * fs_mains * t)
        current_2 += i_peak * rel_amp * np.sin(
            2 * np.pi * k_harm * fs_mains * t - 2 * np.pi / 3.0
        )

    # Signature barres rotor cassees : bandes laterales a fs ± 2*s*fr et
    # 2fs ± 2*s*fr. Amplitude typique 0.5 a 2% du fondamental MCSA (cf.
    # theorie_reference.md §4 "signature beaucoup plus faible en amplitude
    # que côté vibratoire").
    if config["rotor_bar_severity"] > 0:
        for fund in (fs_mains, 2 * fs_mains):
            current_1 += (
                i_peak
                * 0.01
                * config["rotor_bar_severity"]
                * np.sin(2 * np.pi * (fund - 2 * slip * fr_hz) * t)
            )
            current_1 += (
                i_peak
                * 0.006
                * config["rotor_bar_severity"]
                * np.sin(2 * np.pi * (fund + 2 * slip * fr_hz) * t)
            )
            current_2 += (
                i_peak
                * 0.01
                * config["rotor_bar_severity"]
                * np.sin(2 * np.pi * (fund - 2 * slip * fr_hz) * t - 2 * np.pi / 3.0)
            )
            current_2 += (
                i_peak
                * 0.006
                * config["rotor_bar_severity"]
                * np.sin(2 * np.pi * (fund + 2 * slip * fr_hz) * t - 2 * np.pi / 3.0)
            )

    # Bruit de mesure TC (transformateur de courant) : 1/f^1.5 typique
    # (le TC a une bande passante limitée qui atténue le HF).
    current_1 += 0.05 * rated_current_a * 0.01 * colored_noise(n, alpha=1.5, rng=rng)
    current_2 += 0.05 * rated_current_a * 0.01 * colored_noise(n, alpha=1.5, rng=rng)

    # ------------------------------------------------------------------
    # CANAL TACHYMETRE (0/1, 1 pulse par tour)
    # ------------------------------------------------------------------
    tacho = tacho_pulse_train(n, fr_hz, fs, duty=0.1)

    return {
        "vibration": vibration,
        "current_1": current_1,
        "current_2": current_2,
        "tacho": tacho,
    }


def motor_diagnostic_summary(signals: dict[str, np.ndarray], fs: int) -> dict[str, Any]:
    """Calcule un resume diagnostique rapide d'un run moteur.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Sortie de `simulate_motor` ou dict compatible.
    fs : int
        Frequence d'echantillonnage.

    Returns
    -------
    dict
        Resume avec les features temporelles principales (RMS vibration,
        kurtosis) et un check MCSA (presence d'une raie a fs=50 Hz dans
        le courant, et amplitude relative pic secteur / nominal).
    """
    from src.features.time_domain import kurtosis as kurt_fn

    vib = signals["vibration"]
    i1 = signals["current_1"]
    vib_rms = rms(vib)
    vib_kurt = kurt_fn(vib)
    i_rms = rms(i1)
    return {
        "vibration_rms_g": vib_rms,
        "vibration_kurtosis": vib_kurt,
        "current_rms_a": i_rms,
        "duration_s": len(vib) / fs,
        "n_samples": int(len(vib)),
    }
