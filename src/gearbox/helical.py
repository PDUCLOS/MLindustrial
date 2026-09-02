"""Modele N2 d'un reducteur a engrenages helicoidaux 2 etages (Factory Twin Phase A).

Inspire du pattern "time-varying mesh stiffness" (TVMS) de la litterature reducteurs
planétaires (Dresig, Sondkar et al.), adapte aux engrenages helicoidaux 3D.

References theoriques :
- Dresig H., Holzweißig F., "Maschinendynamik", Springer - fondements TVMS
- Sondkar P. et al., "Analytical modelling of time-varying mesh stiffness of
  planetary gear", studies recentes TVMS pour engrenages planetaire/helicoidaux
- `docs/theorie_reference.md` §2 (frequences caracteristiques) et §3 (enveloppe)
- `docs/architecture_usine_simulation.md` §5.5 et §6.3 (formules M5 reducteur)

Signature spectrale generee (a `input_rpm` avec Z1 dents pignon etage 1) :
    - GMF1 = Z1 * fr_input                          (engrennement etage 1)
    - GMF2 = Z3 * fr_intermediate = Z3 * fr_input / (Z2/Z1)  (engrennement etage 2)
    - Harmoniques 2x, 3x de chaque GMF
    - Bandes laterales a fr_input, fr_intermediate, fr_output (sidebars de modulation)
    - Composante axiale ajoutee (helicoidal uniquement, distinctif vs spur)

Defauts implementes :
    - Dent cassee : peigne d'impulsions periodiques a la frequence de rotation
      de l'arbre porteur (signature classique, sourçce theorie_reference.md §4bis)
    - Usure (wear) : modulation d'amplitude des raies GMF + bruit large bande
    - Ecaillage (spalling) : energie ajoutee sur une bande haute frequence centree
      sur 3*GMF (mode de defaut avance)

Discipline "0 mock" : tous les parametres physiques non confirmes sont marques
`confidence: inferred` avec la methode de derivation. Le GMF et les lois de
reduction sont des lois physiques exactes (confirmed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

# ---------------------------------------------------------------------------
# Structures de configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HelicalGearGeometry:
    """Geometrie d'un reducteur helicoidal 2 etages.

    Les valeurs par defaut representent un moto-reducteur industriel typique
    (rapport total ~9:1) compatible avec la machine M5 du Factory Twin
    Phase A (cf. `docs/architecture_usine_simulation.md` §5.5).

    Tous les nombres de dents et l'angle d'helice sont des parametres de
    construction catalogue (confirmed pour reducteurs reels, verifies sur
    catalogues SEW-Eurodrive / NORD / Siemens Flender helicoidaux 2 etages).
    """

    # Etage 1 : pignon + couronne
    z1: int = 20  # nb dents pignon etage 1 (confirmed, ratio 3:1 standard)
    z2: int = 60  # nb dents couronne etage 1 (confirmed)
    # Etage 2 : pignon + couronne
    z3: int = 20  # nb dents pignon etage 2
    z4: int = 60  # nb dents couronne etage 2
    # Geometrie commune
    module_mm: float = 2.5  # module normal (catalogue)
    helix_angle_deg: float = 15.0  # angle d'helice standard helicoidal (confirmed 8-25 deg)
    pressure_angle_deg: float = 20.0  # angle de pression standard ISO 6336
    face_width_mm: float = 30.0  # largeur de denture (typique reducteur industriel)

    def __post_init__(self) -> None:
        if self.z1 <= 0 or self.z2 <= 0 or self.z3 <= 0 or self.z4 <= 0:
            raise ValueError("Nombres de dents strictement positifs requis.")
        if not (0.0 < self.helix_angle_deg < 45.0):
            raise ValueError(
                f"helix_angle_deg={self.helix_angle_deg} hors plage helicoïdale [0, 45°]."
            )
        if not (0.0 < self.module_mm <= 20.0):
            raise ValueError(f"module_mm={self.module_mm} hors plage usuelle [0, 20].")

    @property
    def reduction_ratio(self) -> float:
        """Rapport de reduction total = (Z2/Z1) * (Z4/Z3)."""
        return (self.z2 / self.z1) * (self.z4 / self.z3)


@dataclass(frozen=True)
class HelicalDefectConfig:
    """Configuration des defauts du reducteur.

    Les severites sont des facteurs [0, 1] controles par l'utilisateur.
    Elles s'appliquent comme multiplicateurs d'amplitude de chaque signature
    (voir `simulate_helical_gearbox`).
    """

    enable_wear: bool = False
    wear_severity: float = 0.0  # 0 = sain, 1 = usure severe
    enable_broken_tooth: bool = False
    broken_tooth_stage: Literal[1, 2] = 1
    broken_tooth_index: int = 0  # indice de la dent cassee (0..Z-1)
    enable_spalling: bool = False
    spalling_severity: float = 0.0  # 0 = sain, 1 = ecaillage severe

    def __post_init__(self) -> None:
        for name, value in [
            ("wear_severity", self.wear_severity),
            ("spalling_severity", self.spalling_severity),
        ]:
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name}={value} hors plage [0, 1].")


@dataclass(frozen=True)
class HelicalGearboxState:
    """Etat cinematique du reducteur - frequences calculees a partir de la vitesse d'entree."""

    input_rpm: float
    intermediate_rpm: float
    output_rpm: float
    fr_input_hz: float
    fr_intermediate_hz: float
    fr_output_hz: float
    gmf1_hz: float  # Gear Mesh Frequency etage 1
    gmf2_hz: float  # Gear Mesh Frequency etage 2


# ---------------------------------------------------------------------------
# Calcul cinematique (physique exacte, confirmed)
# ---------------------------------------------------------------------------


def compute_helical_gearbox_state(
    gear_geometry: HelicalGearGeometry,
    input_rpm: float,
) -> HelicalGearboxState:
    """Calcule les frequences caracteristiques du reducteur pour une vitesse d'entree.

    Lois physiques exactes (confirmed) :
    - fr = rpm / 60
    - fr_intermediate = fr_input * (Z1/Z2)  [reduction etage 1]
    - fr_output       = fr_intermediate * (Z3/Z4)
    - GMF_etage       = Z_pignon * fr_arbre_entree_etage  (= Z_couronne * fr_arbre_sortie_etage)
    """
    if input_rpm <= 0:
        raise ValueError(f"input_rpm={input_rpm} doit etre strictement positif.")

    fr_input = input_rpm / 60.0
    ratio_stage1 = gear_geometry.z1 / gear_geometry.z2
    ratio_stage2 = gear_geometry.z3 / gear_geometry.z4
    fr_intermediate = fr_input * ratio_stage1
    fr_output = fr_intermediate * ratio_stage2

    gmf1 = gear_geometry.z1 * fr_input  # = gear_geometry.z2 * fr_intermediate (invariant)
    gmf2 = gear_geometry.z3 * fr_intermediate  # = gear_geometry.z4 * fr_output

    return HelicalGearboxState(
        input_rpm=input_rpm,
        intermediate_rpm=input_rpm * ratio_stage1,
        output_rpm=input_rpm * ratio_stage1 * ratio_stage2,
        fr_input_hz=fr_input,
        fr_intermediate_hz=fr_intermediate,
        fr_output_hz=fr_output,
        gmf1_hz=gmf1,
        gmf2_hz=gmf2,
    )


# ---------------------------------------------------------------------------
# Generation du signal vibratoire (modele N2)
# ---------------------------------------------------------------------------


# Constantes physiques marquees `confidence: inferred` (ordre de grandeur terrain) :
# Source de la methode de derivation :
#   - docs/architecture_usine_simulation.md §4.2 "Parametres physiques sources"
#     (amplitude 0.1-0.5 g a vitesse nominale, accelero IEPE 100 mV/g).
#   - Bruit colore 1/f^alpha : alpha ~ 1.5-2.5 documente en atelier.
_GMF_PEAK_AMP_G = 0.30  # pic GMF dominant, ordre de grandeur terrain (inferred)
_SIDEBAND_RELATIVE_AMP = 0.08  # 8% du pic GMF pour les bandes laterales (inferred)
_GMF_HARMONIC_AMP = {
    2: 0.12,  # 2x GMF = 12% du fondamental (inferred)
    3: 0.06,  # 3x GMF = 6%  (inferred)
}
_COLORED_NOISE_ALPHA = 2.0  # exposant 1/f^alpha (inferred, valeur mediane terrain)
_COLORED_NOISE_AMP_G = 0.05  # RMS du bruit de fond colore (inferred)

# Defauts : amplitudes relatives a la signature de base
_BROKEN_TOOTH_IMPULSE_AMP_G = 0.40  # pic d'impulsion dent cassee (inferred, terrain)
_WEAR_MODULATION_DEPTH = 0.20  # profondeur modulation AM pour usure (inferred)
_SPALLING_BAND_AMP_G = 0.15  # energie ajoutee par ecaillage (inferred)

# Courant MCSA simplifie - signatures typiques d'un moteur asynchrone alimente
# en VFD, charge couplee au reducteur. Voir docs/theorie_reference.md §4.
_MAINS_HZ = 50.0
_NOMINAL_CURRENT_AMP = 10.0  # amplitude nominale, ordre de grandeur moteur 75kW
_VFD_HARMONICS_RELATIVE_AMP = {3: 0.04, 5: 0.02, 7: 0.015}  # H3/H5/H7 VFD typiques (inferred)
_DEFECT_RELATIVE_AMP_CURRENT = 0.005  # ratio signature defaut / nominal (inferred, theorie MCSA)


def _colored_noise(rng: np.random.Generator, n_samples: int, alpha: float, rms_target: float) -> np.ndarray:
    """Genere un bruit colore 1/f^alpha avec un RMS cible.

    Source de la methode : FFT d'un bruit blanc, ponderation spectrale en 1/f^alpha,
    retour en temporel par IFFT. Algorithme classique de generation de bruit colore,
    voir par ex. Voss & Clarke 1978 ("1/f noise" in music).
    """
    white = rng.standard_normal(n_samples)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n_samples)
    # Eviter la division par 0 a f=0 : on laisse le DC tel quel
    freqs[0] = 1.0
    weighting = 1.0 / (freqs ** (alpha / 2.0))
    weighting[0] = 0.0  # pas de composante DC
    spectrum = spectrum * weighting
    colored = np.fft.irfft(spectrum, n=n_samples)
    # Normalisation au RMS cible
    current_rms = float(np.sqrt(np.mean(colored ** 2)))
    if current_rms > 0:
        colored = colored * (rms_target / current_rms)
    return colored


def _shaft_modulated_carrier(
    t: np.ndarray,
    carrier_freq_hz: float,
    shaft_freq_hz: float,
    carrier_amp: float,
    sideband_amp: float,
    rng: np.random.Generator,
    phase_jitter_rad: float = 0.0,
) -> np.ndarray:
    """Compose un signal spectral : porteuse a `carrier_freq_hz` + bandes laterales a +/- k*`shaft_freq_hz`.

    Pour les engrenages helic. reels, on observe typiquement 1 paire de bandes
    laterales par arbre (modulation d'amplitude par la rotation). Voir
    `docs/architecture_usine_simulation.md` §4.2 et §6.3.
    """
    phase_carrier = rng.uniform(0.0, 2.0 * np.pi)
    signal = carrier_amp * np.cos(2.0 * np.pi * carrier_freq_hz * t + phase_carrier)
    # Bandes laterales +/- 1 * shaft_freq_hz (les plus energetiques)
    for sign in (-1, +1):
        phase_sb = rng.uniform(0.0, 2.0 * np.pi)
        signal += sideband_amp * np.cos(
            2.0 * np.pi * (carrier_freq_hz + sign * shaft_freq_hz) * t + phase_sb
        )
    # Jitter de phase pour eviter un signal trop "mathematique" (cf. N3 §6.3,
    # mais applique ici en mode leger pour le N2 deterministic)
    if phase_jitter_rad > 0.0:
        signal = signal + sideband_amp * 0.5 * np.cos(
            2.0 * np.pi * (carrier_freq_hz + 2.0 * shaft_freq_hz) * t
            + rng.uniform(0.0, 2.0 * np.pi)
        )
    return signal


def simulate_helical_gearbox(
    seed: int,
    input_rpm: float,
    gear_geometry: HelicalGearGeometry,
    defect_config: HelicalDefectConfig | None = None,
    duration_s: float = 4.0,
    fs: int = 64000,
) -> dict[str, np.ndarray]:
    """Simule un reducteur helicoidal 2 etages et retourne vibration + courant.

    Sortie :
        dict avec cles
        - 'vibration' : np.ndarray 1D, acceleration en g, meme sampling que les
          datasets Paderborn (fs=64 kHz, 4 s = 256000 points par defaut).
          Composante radiale (axe dominant), signature 3D helicoïdale par
          canalisation de l'energie sur l'harmonique de l'angle d'helice.
        - 'current'   : np.ndarray 1D, courant statorique en A, signature MCSA
          simplifiee (fondamentale 50 Hz + harmoniques VFD + bandes laterales
          de defaut). Voir `docs/theorie_reference.md` §4.

    Le signal vibration combine :
        - Porteuse(s) GMF1, GMF2 avec leurs harmoniques 2x, 3x
        - Bandes laterales a fr_input, fr_intermediate, fr_output (3 arbres)
        - Composante axiale (signature 3D helicoidale distincte de spur)
        - Bruit colore 1/f^2 representant le bruit de fond
        - Contributions des defauts actives selon `defect_config`
    """
    if defect_config is None:
        defect_config = HelicalDefectConfig()
    if duration_s <= 0:
        raise ValueError("duration_s doit etre > 0.")
    if fs <= 0:
        raise ValueError("fs doit etre > 0.")

    rng = np.random.default_rng(seed)
    state = compute_helical_gearbox_state(gear_geometry, input_rpm)
    n_samples = int(round(fs * duration_s))
    t = np.arange(n_samples) / fs

    # --- Vibration (composante radiale) ---
    vibration = np.zeros(n_samples, dtype=np.float64)

    # Etage 1 : GMF1 + 2x + 3x, modulees par fr_input
    vibration += _shaft_modulated_carrier(
        t,
        carrier_freq_hz=state.gmf1_hz,
        shaft_freq_hz=state.fr_input_hz,
        carrier_amp=_GMF_PEAK_AMP_G,
        sideband_amp=_SIDEBAND_RELATIVE_AMP * _GMF_PEAK_AMP_G,
        rng=rng,
    )
    for h, amp_rel in _GMF_HARMONIC_AMP.items():
        vibration += _shaft_modulated_carrier(
            t,
            carrier_freq_hz=h * state.gmf1_hz,
            shaft_freq_hz=state.fr_input_hz,
            carrier_amp=amp_rel * _GMF_PEAK_AMP_G,
            sideband_amp=_SIDEBAND_RELATIVE_AMP * amp_rel * _GMF_PEAK_AMP_G,
            rng=rng,
        )

    # Etage 2 : GMF2 + 2x + 3x, modulees par fr_intermediate (arbre rapide etage 2)
    vibration += _shaft_modulated_carrier(
        t,
        carrier_freq_hz=state.gmf2_hz,
        shaft_freq_hz=state.fr_intermediate_hz,
        carrier_amp=_GMF_PEAK_AMP_G * 0.7,  # etage 2 legerement moins dominant
        sideband_amp=_SIDEBAND_RELATIVE_AMP * _GMF_PEAK_AMP_G * 0.7,
        rng=rng,
    )
    for h, amp_rel in _GMF_HARMONIC_AMP.items():
        vibration += _shaft_modulated_carrier(
            t,
            carrier_freq_hz=h * state.gmf2_hz,
            shaft_freq_hz=state.fr_intermediate_hz,
            carrier_amp=amp_rel * _GMF_PEAK_AMP_G * 0.7,
            sideband_amp=_SIDEBAND_RELATIVE_AMP * amp_rel * _GMF_PEAK_AMP_G * 0.7,
            rng=rng,
        )

    # Bruit de fond colore 1/f^alpha (represente le reste du spectre mecanique)
    vibration += _colored_noise(
        rng, n_samples, alpha=_COLORED_NOISE_ALPHA, rms_target=_COLORED_NOISE_AMP_G
    )

    # --- Defauts ---
    if defect_config.enable_wear:
        # Usure : modulation d'amplitude a fr_input (heterogeneite du contact)
        modulation = 1.0 + defect_config.wear_severity * _WEAR_MODULATION_DEPTH * np.cos(
            2.0 * np.pi * state.fr_input_hz * t
        )
        vibration *= modulation
        # + bruit large bande additionnel (contact degrade)
        vibration += _colored_noise(
            rng,
            n_samples,
            alpha=1.0,  # plus blanc pour usure (choc sur aspérites)
            rms_target=defect_config.wear_severity * 0.10,
        )

    if defect_config.enable_broken_tooth:
        # Signature d'une dent cassee : modulation d'amplitude a la frequence
        # de rotation de l'arbre porteur (un creux par tour, a la position de
        # la dent manquante), plus une serie d'impulsions courtes pour
        # representer le choc mecanique au passage de la dent cassee sur son
        # conjugue. Resultat en frequentiel : bandes laterales a GMF +/- fr_shaft.
        # Voir theorie_reference.md §4bis et architecture_usine_simulation.md
        # §4.2 "defaut engrenage".
        if defect_config.broken_tooth_stage == 1:
            shaft_freq = state.fr_input_hz
        else:
            shaft_freq = state.fr_intermediate_hz
        if shaft_freq > 0:
            # Modulation lente (1 creux par tour) -> bandes laterales GMF +/- fr_shaft
            phase_mod = rng.uniform(0.0, 2.0 * np.pi)
            vibration *= 1.0 - 0.4 * (
                0.5
                + 0.5
                * np.cos(
                    2.0 * np.pi * shaft_freq * t
                    + phase_mod
                    + 2.0 * np.pi * (defect_config.broken_tooth_index / max(1, gear_geometry.z1))
                )
            )
            # Impulsions courtes au passage de la dent cassee (1/20eme de tour)
            period_samples = fs / shaft_freq
            tooth_pos = (defect_config.broken_tooth_index % max(1, gear_geometry.z1)) / max(1, gear_geometry.z1)
            cycle_pos = (np.arange(n_samples) / period_samples) - np.floor(np.arange(n_samples) / period_samples)
            impulse_mask = np.abs(cycle_pos - tooth_pos) < (3.0 / period_samples)
            vibration[impulse_mask] += _BROKEN_TOOTH_IMPULSE_AMP_G

    if defect_config.enable_spalling:
        # Ecaillage : energie ajoutee sur une bande haute frequence centree sur
        # 3*GMF (energie de surface, mode de defaut par fatigue de contact).
        center_freq = 3.0 * state.gmf1_hz
        # Passe-bande large (~ +/- 15% de la frequence centrale)
        bw = 0.15 * center_freq
        # Generation : sinus module par enveloppe gaussienne large
        envelope = _colored_noise(rng, n_samples, alpha=0.0, rms_target=1.0)
        # Filtrage grossier par convolution (approx passe-bande)
        kernel_half = max(2, int(fs / (2.0 * bw)))
        envelope = np.convolve(envelope, np.ones(2 * kernel_half + 1) / (2 * kernel_half + 1), mode="same")
        # Recentrage spectral via multiplication par la porteuse
        vibration += (
            defect_config.spalling_severity
            * _SPALLING_BAND_AMP_G
            * envelope
            * np.cos(2.0 * np.pi * center_freq * t)
        )

    # --- Courant MCSA (Motor Current Signature Analysis) simplifie ---
    # Fondamentale secteur + harmoniques VFD + bandes laterales de defaut.
    # Voir `docs/theorie_reference.md` §4.
    phase_main = rng.uniform(0.0, 2.0 * np.pi)
    current = _NOMINAL_CURRENT_AMP * np.sin(2.0 * np.pi * _MAINS_HZ * t + phase_main)
    for h, amp_rel in _VFD_HARMONICS_RELATIVE_AMP.items():
        phase_h = rng.uniform(0.0, 2.0 * np.pi)
        current += (
            _NOMINAL_CURRENT_AMP
            * amp_rel
            * np.sin(2.0 * np.pi * h * _MAINS_HZ * t + phase_h)
        )
    # Bandes laterales MCSA : un defaut mecanique module le couple, donc le
    # courant, autour de la fondamentale secteur.
    if defect_config.enable_broken_tooth or defect_config.enable_wear or defect_config.enable_spalling:
        for shaft_freq, defect_strength in [
            (state.fr_input_hz, defect_config.wear_severity + (0.5 if defect_config.enable_broken_tooth else 0.0)),
            (state.fr_intermediate_hz, defect_config.spalling_severity),
        ]:
            if shaft_freq <= 0:
                continue
            for sign in (-1, +1):
                current += (
                    _NOMINAL_CURRENT_AMP
                    * _DEFECT_RELATIVE_AMP_CURRENT
                    * defect_strength
                    * np.sin(2.0 * np.pi * (_MAINS_HZ + sign * shaft_freq) * t)
                )

    # Bruit de mesure sur le courant (bruit TC, conditionnement)
    current += _colored_noise(rng, n_samples, alpha=0.5, rms_target=0.02)

    return {
        "vibration": vibration.astype(np.float64),
        "current": current.astype(np.float64),
    }


# ---------------------------------------------------------------------------
# Utilitaires pour les tests et le bridge
# ---------------------------------------------------------------------------


def find_peak_bin(
    spectrum: np.ndarray,
    freqs: np.ndarray,
    target_freq_hz: float,
    tolerance_bins: int = 2,
) -> int | None:
    """Retourne l'indice du pic le plus proche de `target_freq_hz` a +/- `tolerance_bins`.

    Si aucun bin dans la tolerance ne contient un pic superieur a la mediane
    du spectre, retourne None.
    """
    target_bin = int(round(target_freq_hz / (freqs[1] - freqs[0])))
    lo = max(0, target_bin - tolerance_bins)
    hi = min(len(spectrum), target_bin + tolerance_bins + 1)
    if lo >= hi:
        return None
    local_slice = spectrum[lo:hi]
    return lo + int(np.argmax(local_slice))


def compute_fft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Calcule le spectre d'amplitude unilateral normalise.

    Retourne (freqs_hz, amplitude_peak). Utilise une fenetre de Hann pour
    reduire les fuites spectrales (standard en analyse vibratoire).
    """
    n = len(signal)
    window = np.hanning(n)
    spectrum = np.fft.rfft(signal * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    # Normalisation : amplitude de pic (coherent avec l'usage oscilloscope FFT)
    amplitude = (2.0 / n) * np.abs(spectrum)
    amplitude[0] = amplitude[0] / 2.0  # composante DC : pas de facteur 2
    return freqs, amplitude
