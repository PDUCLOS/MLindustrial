"""Modele N2 d'une pompe centrifuge 30 kW a 3000 tr/min.

Cible : SA5 du CDC (`docs/CDC_projet.md` §6.1, ligne "SA5 modeles
convoyeur + presse + pompe"), machine M2 du Factory Twin Phase A (cf.
`docs/architecture_usine_simulation.md` §5.2 et tableau §3).

Le modele N2 genere simultanement :
- un signal d'acceleration vibratoire (g), canal "vibration" - aligne
  format Paderborn (4 s a 64 kHz, 256 000 points)
- un signal de pression refoulement (bar), canal "pressure" - signature
  lente avec ondulation de pompage a 1x fr
- un signal de debit (m^3/h), canal "flow" - debit nominal + ondulation
  1x fr (asymetrie pale/volute)
- un signal de temperature (degC), canal "temperature" - derive lente
  liee a l'echauffement + bruit blanc

Defauts implementes :
- balourd / desalignement (raies 1x, 2x fr, comme pour toute machine
  tournante, cf. `docs/theorie_reference.md` §4bis)
- defauts roulement 6206 (BPFO/BPFI/BSF) - palette
  de roulements standards pour palier de pompe 30 kW, cf. entree
  `6206` dans `configs/bearing_geometry.yaml`
- cavitation (bande large 5-15 kHz, cf. §5.2 du CDC architecture) -
  c'est le defaut SPECIFIQUE pompe, signature tres differente des
  roulements (pas de raie discrete, energie etalee sur ~10 kHz)
- usure garniture mecanique (augmentation du bruit large bande sans
  structure spectrale nette)

Parametres physiques et leur source :
- vitesse 3000 rpm / 50 Hz (2 poles) : norme IEC 60034-1
  (`confidence: confirmed` dans tableau §10 du doc architecture)
- plage cavitation 5-15 kHz : `confidence: inferred`, derivee de la
  litterature pumps (Karassik, Messina - cf. tableau §10 du doc
  architecture ligne "Cavitation BW")
- amplitude vibration en g sain 0.1-10 g : `confidence: inferred`,
  ordre de grandeur mesures terrain
- amplitudes BPFO/BPFI/BSF : `inferred`, derivees de l'ordre de
  grandeur ISO 10816 zone A (0.1-0.5 g sain)
- amplitudes pression/debit/temperature : `inferred`, ordres de
  grandeur typiques d'une pompe centrifuge industrielle 30 kW
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

# Pression de refoulement nominale (bar). Ordre de grandeur pompe
# centrifuge 30 kW / 3000 rpm en application industrielle standard.
# `confidence: inferred`.
DEFAULT_RATED_PRESSURE_BAR: float = 4.0

# Debit nominal (m^3/h). Ordre de grandeur typique pour 30 kW.
# `confidence: inferred`.
DEFAULT_RATED_FLOW_M3H: float = 50.0

# Temperature de service nominale (degC). `confidence: inferred`.
DEFAULT_OPERATING_TEMP_C: float = 60.0

# Bande de frequence de la signature cavitation (Hz). Cf. CDC architecture
# §5.2 : "large_bande_5_15kHz". `confidence: inferred` (cite Karassik).
CAVITATION_BAND_HZ: tuple[float, float] = (5000.0, 15000.0)

# Amplitude crete vibration des 1x/2x fr (g) pour une pompe saine.
# Ordre de grandeur ISO 10816 zone A pour une pompe 30 kW.
# `confidence: inferred`.
_BASE_HARMONIC_AMP_G: tuple[float, ...] = (0.20, 0.08, 0.03, 0.01)


def simulate_pump(
    seed: int,
    rpm: float,
    defect_config: dict[str, float] | None = None,
    duration_s: float = 4.0,
    fs: int = 64000,
    bearing_key: str = "6206",
    rated_pressure_bar: float = DEFAULT_RATED_PRESSURE_BAR,
    rated_flow_m3h: float = DEFAULT_RATED_FLOW_M3H,
    operating_temp_c: float = DEFAULT_OPERATING_TEMP_C,
) -> dict[str, np.ndarray]:
    """Simule une pompe centrifuge 30 kW (modele N2 deterministe).

    Parameters
    ----------
    seed : int
        Graine du generateur aleatoire.
    rpm : float
        Vitesse de rotation mecanique (tr/min). Pour 2 poles 50 Hz,
        plage utile ~2900-3100 tr/min en charge nominale.
    defect_config : dict[str, float] or None, optional
        Severite par defaut (cf. `default_defect_config()`).
    duration_s : float, optional
        Duree du signal (defaut 4.0, aligne Paderborn).
    fs : int, optional
        Frequence d'echantillonnage (defaut 64000, aligne Paderborn).
    bearing_key : str, optional
        Cle YAML du roulement palier (defaut "6206").
    rated_pressure_bar : float, optional
        Pression de refoulement nominale (defaut 4.0 bar).
    rated_flow_m3h : float, optional
        Debit nominal (defaut 50 m^3/h).
    operating_temp_c : float, optional
        Temperature de service (defaut 60 degC).

    Returns
    -------
    dict[str, np.ndarray]
        - 'vibration' (g)
        - 'pressure' (bar), pression refoulement
        - 'flow' (m^3/h), debit
        - 'temperature' (degC)
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

    # ------------------------------------------------------------------
    # CANAL VIBRATION (g)
    # ------------------------------------------------------------------
    vibration = np.zeros(n)

    # (1) Rotation de base : 1x, 2x, 3x, 4x fr.
    for k, amp in enumerate(_BASE_HARMONIC_AMP_G, start=1):
        if k == 1:
            effective_amp = amp * (1.0 + 4.0 * config["unbalance_severity"])
        elif k == 2:
            # 2x dominant en desalignement angulaire (cf. theorie_reference §4bis)
            effective_amp = amp * (1.0 + 3.0 * config["misalignment_severity"])
        else:
            effective_amp = amp
        vibration += effective_amp * np.sin(2 * np.pi * k * fr_hz * t + rng.uniform(0, 2 * np.pi))

    # (2) Defauts roulement 6206.
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

    # (3) Cavitation : bande large 5-15 kHz, PAS de raie discrete.
    # Implementation par un bruit blanc filtre passe-bande (Butterworth).
    if config["cavitation_severity"] > 0:
        cav_low, cav_high = CAVITATION_BAND_HZ
        nyq = fs / 2.0
        # Coefficients Butterworth d'ordre 4 (cavitation : signature large
        # bande avec peu de structure fine, ordre modéré suffit).
        from scipy.signal import butter, sosfiltfilt

        sos = butter(4, [cav_low / nyq, min(cav_high, nyq * 0.99) / nyq], btype="band", output="sos")
        white = rng.standard_normal(n)
        cavitation_noise = sosfiltfilt(sos, white)
        # Normalisation puis amplitude en g (0.1 a 2 g selon severite,
        # cf. CDC §5.2 severity_range [0.1, 2.0]).
        cavitation_noise = cavitation_noise / np.std(cavitation_noise) * (
            0.5 + 1.5 * config["cavitation_severity"]
        )
        vibration += cavitation_noise

    # (4) Usure garniture mecanique : bruit large bande supplementaire,
    # pas de raie discrete, distribution spectrale "plate".
    if config["seal_wear_severity"] > 0:
        vibration += 0.3 * config["seal_wear_severity"] * colored_noise(n, alpha=0.8, rng=rng)

    # (5) Bruit de fond general 1/f^1.5 (un peu moins "rouge" qu'un moteur
    # car moins de sources mecaniques large bande sur une pompe).
    vibration += 0.02 * colored_noise(n, alpha=1.5, rng=rng)

    # ------------------------------------------------------------------
    # CANAL PRESSION (bar) - refoulement
    # ------------------------------------------------------------------
    # Ondulation de pompage : 1x fr (passage des aubes de la volute) avec
    # amplitude ~5% de la pression nominale.
    pressure = rated_pressure_bar * (
        1.0
        + 0.05 * np.sin(2 * np.pi * fr_hz * t + rng.uniform(0, 2 * np.pi))
        + 0.01 * np.sin(2 * np.pi * 2 * fr_hz * t + rng.uniform(0, 2 * np.pi))
    )
    # La cavitation induit des chutes de pression brusques (collapse de
    # bulles) - on les modelise par un bruit blanc additionnel.
    if config["cavitation_severity"] > 0:
        pressure += 0.2 * config["cavitation_severity"] * rated_pressure_bar * rng.standard_normal(n)
    # L'usure garniture fait chuter la pression moyenne (fuite interne).
    if config["seal_wear_severity"] > 0:
        pressure *= 1.0 - 0.15 * config["seal_wear_severity"]

    # ------------------------------------------------------------------
    # CANAL DEBIT (m^3/h)
    # ------------------------------------------------------------------
    # Debit nominal + ondulation 1x fr (pulse par pale de la roue).
    n_blades = 6  # roue centrifuge standard 6 aubes, ordre de grandeur
    flow = rated_flow_m3h * (
        1.0
        + 0.08 * np.sin(2 * np.pi * n_blades * fr_hz * t + rng.uniform(0, 2 * np.pi))
        + 0.02 * np.sin(2 * np.pi * fr_hz * t + rng.uniform(0, 2 * np.pi))
    )
    # Bruit de mesure debitmetre.
    flow += 0.02 * rated_flow_m3h * rng.standard_normal(n)
    # L'usure garniture fait chuter le debit (fuite).
    if config["seal_wear_severity"] > 0:
        flow *= 1.0 - 0.10 * config["seal_wear_severity"]

    # ------------------------------------------------------------------
    # CANAL TEMPERATURE (degC)
    # ------------------------------------------------------------------
    # Temperature de service + derive lente (echauffement) + bruit blanc
    # (capteur Pt100).
    drift_rate_c_per_s = 0.05  # +3 degC sur 60 s, `confidence: inferred`
    temperature = (
        operating_temp_c
        + drift_rate_c_per_s * t
        + 0.1 * np.sin(2 * np.pi * 0.05 * t)  # fluctuation tres lente
        + 0.05 * rng.standard_normal(n)
    )
    # Echauffement anormal en cas d'usure garniture (frottement sec).
    if config["seal_wear_severity"] > 0:
        temperature += 5.0 * config["seal_wear_severity"]

    return {
        "vibration": vibration,
        "pressure": pressure,
        "flow": flow,
        "temperature": temperature,
    }


def pump_diagnostic_summary(signals: dict[str, np.ndarray], fs: int) -> dict[str, Any]:
    """Calcule un resume diagnostique rapide d'un run pompe.

    Parameters
    ----------
    signals : dict[str, np.ndarray]
        Sortie de `simulate_pump`.
    fs : int
        Frequence d'echantillonnage.

    Returns
    -------
    dict
        Features temporelles principales + moyennes des canaux lents
        (pression, debit, temperature).
    """
    from src.features.time_domain import kurtosis as kurt_fn

    vib = signals["vibration"]
    return {
        "vibration_rms_g": rms(vib),
        "vibration_kurtosis": kurt_fn(vib),
        "pressure_mean_bar": float(np.mean(signals["pressure"])),
        "flow_mean_m3h": float(np.mean(signals["flow"])),
        "temperature_mean_c": float(np.mean(signals["temperature"])),
        "duration_s": len(vib) / fs,
        "n_samples": len(vib),
    }
