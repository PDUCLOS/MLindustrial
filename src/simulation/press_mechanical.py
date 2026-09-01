"""Modele N2 d'une presse mecanique 100T a 60 cycles/min.

Cible : SA5 du CDC (`docs/CDC_projet.md` §6.1, ligne "SA5 modeles
convoyeur + presse + pompe"), machine M6 du Factory Twin Phase A (cf.
`docs/architecture_usine_simulation.md` §5.3 et tableau §3 ligne M6).

Profil d'un cycle (cf. CDC architecture §3 ligne M6 "Accélération subise
a chaque course") :
- 0% - 15% : embrayage (mise en rotation de la bielle, pic de courant
  et pic d'acceleration)
- 15% - 50% : acceleration de la bielle, approche de la piece
- 50% - 60% : FRAPPE (impact piece, pic d'acceleration tres intense,
  duree courte, contenu HF large bande)
- 60% - 90% : retour, deceleration
- 90% - 100% : frein et attente avant cycle suivant

Le signal de vibration est un CONVOLUTION d'un pattern d'impact cyclique
(repete N fois ou N = nombre de cycles dans la duree du signal) avec
les composantes continues (defauts roulements, desalignement, bruit de
fond).

Defauts implementes :
- defauts roulements 22320 (bielle, spherical roller) et 22220 (palier,
  spherical roller) - cf. entrees YAML ajoutees le 2026-09-01 dans
  `configs/bearing_geometry.yaml`
- desalignement (raies 1x, 2x fr_bielle, cf. §4bis theorie_reference)
- defaut d'embrayage/frein (signature supplementaire - non implemente
  ici, pourrait etre un upgrade futur)

Parametres physiques et leur source :
- frequence de cycle 60 cycles/min = 1 Hz : spec machine M6 du CDC
  architecture, `confidence: confirmed`
- vitesse rotation bielle 200 rpm (3.33 Hz) : `confidence: inferred`
  (ordre de grandeur presse mecanique 100T standard, pas de doc
  constructeur specifique)
- roulements 22320 et 22220 : geometries catalogue SKF CC/W33, cf.
  entree YAML `confidence: inferred`
- amplitudes impacts : `confidence: inferred`, ordre de grandeur
  1-10 g en frappe (cf. CDC architecture §9.1 "RMS vibration 0.1-0.5 g
  sain, 1-5 g defaut severe")
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.features.fault_frequencies import (
    bpfi,
    bpfo,
    bsf,
    rotational_frequency_hz,
)
from src.features.time_domain import rms
from src.simulation._helpers import (
    bearing_geometry_from_yaml,
    bearing_impacts,
    colored_noise,
    default_defect_config,
)

# Vitesse de rotation de la bielle (tr/min). Ordre de grandeur presse
# mecanique 100T standard. `confidence: inferred` (pas de doc constructeur
# pour cette presse simulee).
DEFAULT_CRANKSHAFT_RPM: float = 200.0

# Courant nominal du moteur de la presse (A). Ordre de grandeur moteur
# asynchrone 30-50 kW entraınant une presse 100T. `confidence: inferred`.
DEFAULT_MOTOR_RATED_CURRENT_A: float = 70.0

# Amplitude crete de l'impact d'embrayage (g). `confidence: inferred`.
EMBRAYAGE_AMPLITUDE_G: float = 2.0

# Amplitude crete de l'impact de frappe (g). Plus intense et plus haute
# frequence que l'embrayage. `confidence: inferred`.
FRAPPE_AMPLITUDE_G: float = 8.0

# Frequence centrale de la resonance de l'impact de frappe (Hz). Ordre
# de grandeur structure d'une presse 100T (resonance chassis/bati).
# `confidence: inferred`.
FRAPPE_RESONANCE_HZ: float = 600.0

# Frequence centrale de l'impact d'embrayage (Hz), plus basse (engagement
# progressif). `confidence: inferred`.
EMBRAYAGE_RESONANCE_HZ: float = 150.0

# Decay time de l'impact de frappe (s), `confidence: inferred`.
FRAPPE_DECAY_S: float = 0.02

# Decay time de l'impact d'embrayage (s), `confidence: inferred`.
EMBRAYAGE_DECAY_S: float = 0.05

# Amplitudes des harmoniques 1x/2x fr_bielle (g). `confidence: inferred`.
_BASE_HARMONIC_AMP_G: tuple[float, ...] = (0.30, 0.15, 0.05, 0.02)


def simulate_press(
    seed: int,
    cycle_count: int | None = None,
    defect_config: dict[str, float] | None = None,
    duration_s: float = 4.0,
    fs: int = 64000,
    cycle_freq_hz: float = 1.0,
    crankshaft_rpm: float = DEFAULT_CRANKSHAFT_RPM,
    motor_rated_current_a: float = DEFAULT_MOTOR_RATED_CURRENT_A,
    bearing_keys: tuple[str, str] = ("22320", "22220"),
) -> dict[str, np.ndarray]:
    """Simule une presse mecanique 100T (modele N2 deterministe).

    Parameters
    ----------
    seed : int
        Graine du generateur aleatoire.
    cycle_count : int or None, optional
        Nombre de cycles (coups) contenus dans le signal. Si None,
        calcule automatiquement comme `int(duration_s * cycle_freq_hz)`
        pour avoir un nombre entier de cycles dans la duree.
    defect_config : dict[str, float] or None, optional
        Severite par defaut (cf. `default_defect_config()`).
    duration_s : float, optional
        Duree du signal (defaut 4.0, aligne Paderborn).
    fs : int, optional
        Frequence d'echantillonnage (defaut 64000, aligne Paderborn).
    cycle_freq_hz : float, optional
        Frequence de cycle (Hz). Defaut 1.0 (= 60 cycles/min, spec M6).
    crankshaft_rpm : float, optional
        Vitesse de rotation de l'arbre vilebrequin/bielle (defaut 200 rpm).
    motor_rated_current_a : float, optional
        Courant nominal moteur (defaut 70 A, ordre de grandeur 30-50 kW).
    bearing_keys : tuple[str, str], optional
        Cles YAML des 2 roulements (bielle, palier), defaut
        ("22320", "22220") conformement a la spec M6.

    Returns
    -------
    dict[str, np.ndarray]
        - 'vibration' (g)
        - 'current' (A), courant moteur
    """
    config = default_defect_config()
    if defect_config is not None:
        config.update(defect_config)

    n = int(round(duration_s * fs))
    if n < 2:
        raise ValueError(f"duration_s * fs doit donner >= 2 samples, recu {n}")

    if cycle_count is None:
        cycle_count = int(round(duration_s * cycle_freq_hz))
    if cycle_count < 1:
        raise ValueError(f"cycle_count doit etre >= 1, recu {cycle_count}")

    cycle_period_s = 1.0 / cycle_freq_hz
    rng = np.random.default_rng(seed)
    t = np.arange(n) / fs

    fr_hz = rotational_frequency_hz(crankshaft_rpm)

    # ------------------------------------------------------------------
    # CANAL VIBRATION (g)
    # ------------------------------------------------------------------
    vibration = np.zeros(n)

    # (1) Rotation de la bielle : 1x, 2x, 3x, 4x fr_bielle.
    for k, amp in enumerate(_BASE_HARMONIC_AMP_G, start=1):
        if k == 1:
            effective_amp = amp * (1.0 + 3.0 * config["unbalance_severity"])
        elif k == 2:
            effective_amp = amp * (1.0 + 2.5 * config["misalignment_severity"])
        else:
            effective_amp = amp
        vibration += effective_amp * np.sin(2 * np.pi * k * fr_hz * t + rng.uniform(0, 2 * np.pi))

    # (2) Defauts roulements bielle (22320) et palier (22220).
    for bearing_key in bearing_keys:
        geom = bearing_geometry_from_yaml(bearing_key)
        n_balls = int(geom["n_balls"])
        ball_d_mm = float(geom["ball_diameter_mm"])
        pitch_d_mm = float(geom["pitch_diameter_mm"])
        phi_deg = float(geom.get("contact_angle_deg", 0.0))
        bpfo_hz = bpfo(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)
        bpfi_hz = bpfi(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)
        bsf_hz = bsf(n_balls, fr_hz, ball_d_mm, pitch_d_mm, phi_deg)
        # Spherical roller : impact plus intense que billes (surface de
        # contact lineique, pas ponctuelle) -> amplitude 1.5x.
        vibration += 1.5 * bearing_impacts(
            n, fs, bpfo_hz, amplitude_g=1.0 * config["bearing_outer_severity"], rng=rng
        )
        vibration += 1.2 * bearing_impacts(
            n, fs, bpfi_hz, amplitude_g=0.8 * config["bearing_inner_severity"], rng=rng
        )
        vibration += 0.6 * bearing_impacts(
            n, fs, bsf_hz, amplitude_g=0.4 * config["bearing_roller_severity"], rng=rng
        )

    # (3) Profil cyclique : 1 impact d'embrayage + 1 impact de frappe par
    # cycle. Le pattern est place a t = k * T_cycle + offset, avec un
    # petit jitter (±2% de la periode) pour eviter un signal trop propre.
    for k in range(cycle_count):
        cycle_start = k * cycle_period_s
        # Petit jitter temporel (±2% de la periode de cycle)
        jitter = float(rng.uniform(-0.02, 0.02) * cycle_period_s)
        cycle_start += jitter

        # Impact d'embrayage a 10% du cycle (phase engagement)
        emb_start = cycle_start + 0.10 * cycle_period_s
        vibration += _decaying_impulse(
            t, emb_start, EMBRAYAGE_AMPLITUDE_G, EMBRAYAGE_RESONANCE_HZ, EMBRAYAGE_DECAY_S, fs
        )

        # Impact de frappe a 55% du cycle (piece)
        frappe_start = cycle_start + 0.55 * cycle_period_s
        vibration += _decaying_impulse(
            t, frappe_start, FRAPPE_AMPLITUDE_G, FRAPPE_RESONANCE_HZ, FRAPPE_DECAY_S, fs
        )

    # (4) Bruit de fond general 1/f^1.5 (chassis massif mais avec
    # resonances multiples).
    vibration += 0.03 * colored_noise(n, alpha=1.5, rng=rng)

    # ------------------------------------------------------------------
    # CANAL COURANT MOTEUR (A)
    # ------------------------------------------------------------------
    # Le moteur de la presse a un cycle de charge : courant nominal pendant
    # la course, pics a l'embrayage et a la frappe.
    i_peak_nominal = motor_rated_current_a * np.sqrt(2.0) / np.sqrt(3.0)
    current = np.full(n, i_peak_nominal * 0.6)  # 60% du nominal en regime établi

    # Pics de courant a l'embrayage (2.5x nominal pendant ~50 ms) et a la
    # frappe (3.5x nominal pendant ~30 ms).
    for k in range(cycle_count):
        cycle_start = k * cycle_period_s
        jitter = float(rng.uniform(-0.02, 0.02) * cycle_period_s)
        cycle_start += jitter

        emb_start_idx = int((cycle_start + 0.10 * cycle_period_s) * fs)
        frappe_start_idx = int((cycle_start + 0.55 * cycle_period_s) * fs)

        # Pic embrayage : 2.5x nominal, duree 50 ms
        emb_end_idx = min(emb_start_idx + int(0.050 * fs), n)
        if emb_start_idx < n:
            current[emb_start_idx:emb_end_idx] += i_peak_nominal * (2.5 - 0.6) * np.exp(
                -3.0 * np.arange(emb_end_idx - emb_start_idx) / fs
            )

        # Pic frappe : 3.5x nominal, duree 30 ms (plus court, plus intense)
        frappe_end_idx = min(frappe_start_idx + int(0.030 * fs), n)
        if frappe_start_idx < n:
            current[frappe_start_idx:frappe_end_idx] += i_peak_nominal * (3.5 - 0.6) * np.exp(
                -5.0 * np.arange(frappe_end_idx - frappe_start_idx) / fs
            )

    # Bruit de mesure TC.
    current += 0.01 * motor_rated_current_a * colored_noise(n, alpha=1.5, rng=rng)

    return {
        "vibration": vibration,
        "current": current,
    }


def _decaying_impulse(
    t: np.ndarray,
    t_start: float,
    amplitude_g: float,
    resonance_hz: float,
    decay_time_s: float,
    fs: int,
) -> np.ndarray:
    """Genere un impact sinusoidal amorti (gaussien-like) au temps t_start.

    Utilise pour modeliser les impacts d'embrayage et de frappe de la
    presse. La forme d'onde est : A * exp(-t/tau) * sin(2*pi*f*t) * window,
    avec une fenetre qui tronque a 5*tau (au-dela, l'amplitude est
    inferieure a 1% de la crete).
    """
    out = np.zeros_like(t)
    if t_start < 0 or t_start > t[-1] + 5 * decay_time_s:
        return out

    # Indices concernes (entre t_start et t_start + 5*tau).
    start_idx = max(0, int(t_start * fs))
    end_idx = min(len(t), int((t_start + 5 * decay_time_s) * fs) + 1)
    if end_idx <= start_idx:
        return out

    local_t = t[start_idx:end_idx] - t_start
    envelope = np.exp(-local_t / decay_time_s)
    carrier = np.sin(2 * np.pi * resonance_hz * local_t)
    out[start_idx:end_idx] = amplitude_g * envelope * carrier
    return out


def press_diagnostic_summary(signals: dict[str, np.ndarray], fs: int) -> dict[str, Any]:
    """Calcule un resume diagnostique rapide d'un run presse.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Sortie de `simulate_press`.
    fs : int
        Frequence d'echantillonnage.

    Returns
    -------
    dict
        Features temporelles principales du canal vibration et du courant
        (incluant courant crete, utile pour detecter les pics d'embrayage
        et de frappe).
    """
    from src.features.time_domain import kurtosis as kurt_fn, peak_to_peak

    vib = signals["vibration"]
    cur = signals["current"]
    return {
        "vibration_rms_g": rms(vib),
        "vibration_kurtosis": kurt_fn(vib),
        "vibration_peak_to_peak_g": peak_to_peak(vib),
        "current_rms_a": rms(cur),
        "current_peak_a": float(np.max(np.abs(cur))),
        "duration_s": len(vib) / fs,
        "n_samples": int(len(vib)),
    }
