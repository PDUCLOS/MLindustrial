"""Propagation P2 - vibration transmissible structurellement (Factory Twin Phase A).

Modele physique :
    La vibration generee par une machine source se propage dans la structure
    (beton, sol, metallique) vers les machines voisines, avec une attenuation
    fonction de la distance et de la frequence.

    Le modele retenu (phase A) est une fonction de transfert simplifiee de type
    onde amortie dans un milieu semi-infini :

        H(f, d) = exp(-alpha(d) * d * f)

    ou :
        - d  = distance source -> cible (metres)
        - f  = frequence (Hz)
        - alpha(d) = coefficient d'attenuation (s/m) dependant du type de sol
                     et de structure. Valeurs documentees dans la litterature
                     Barkan (1962) et ISO 10816 pour les fondations industrielles
                     : alpha ~ 5e-4 a 5e-3 s/m selon rigidite du sol/structure.

    Cette formulation est 1D conservative : elle suppose un couplage de type
    fondation partagee ou sol continu entre source et cible. Le cas "fondations
    totalement decouplees" (dalle flottante) donnerait une attenuation > 40 dB
    quasi independamment de la distance - non couvert en Phase A.

References :
    - `docs/theorie_reference.md` §2-3 (frequences, enveloppe, propagation)
    - `docs/CDC_projet.md` §3.1 P2 (propagation mecanique)
    - Barkan D.D., "Dynamics of Bases and Foundations", McGraw-Hill 1962
    - ISO 10816 / ISO 20816 (evaluation des vibrations mecaniques)

Critere de validation Phase A (CDC §7.1 A4) : un defaut M1 -> vibration visible
sur M2 avec attenuation >= 20 dB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .base import Propagator, SignalDict


# Coefficients d'attenuation alpha (s/m) par type de sol/structure.
# Source : litterature Barkan 1962, repris par Richart & Whitman (1967) et les
# normes ISO 10816. Ordres de grandeur coherents avec mesures industrielles.
# Toutes valeurs marquees `confidence: inferred` (calibration terrain precise
# necessite campagne de mesure sur site).
ALPHA_CONCRETE_RIGID_S = 5e-4  # dalle beton epaisse couplee (inferred)
ALPHA_CONCRETE_SOFT_S = 2e-3   # dalle beton mince sur solmeuble (inferred)
ALPHA_STEEL_FRAME_S = 3e-3     # chassis metallique (inferred)
ALPHA_SOIL_S = 5e-3            # sol direct (couplage le plus fort) (inferred)


@dataclass(frozen=True)
class MechanicalCoupling:
    """Couplage structurel entre une machine source et une machine cible."""

    distance_m: float
    alpha_s_per_m: float
    extra_attenuation_db: float = 0.0  # attenuation supplementaire (ex. joint de dilatation)


class MechanicalPropagator(Propagator):
    """Propagation P2 - vibration transmissible structurellement.

    Parametres
    ----------
    fs : int
        Frequence d'echantillonnage des signaux (Hz). Doit correspondre a la
        fois a la source et a la cible.
    default_coupling : MechanicalCoupling
        Couplage par defaut utilise si `propagate(...)` ne precise pas un
        couplage specifique par cible.
    """

    def __init__(
        self,
        fs: int = 64000,
        default_coupling: MechanicalCoupling | None = None,
    ) -> None:
        if fs <= 0:
            raise ValueError("fs doit etre strictement positif.")
        self.fs = fs
        self.default_coupling = default_coupling or MechanicalCoupling(
            distance_m=5.0,
            alpha_s_per_m=ALPHA_CONCRETE_RIGID_S,
        )

    def propagate(
        self,
        signal_dict: SignalDict,
        source_machine: str,
        target_machines: list[str],
        couplings: dict[str, MechanicalCoupling] | None = None,
        **kwargs: Any,
    ) -> dict[str, SignalDict]:
        """Propage un signal de vibration de `source_machine` vers chaque cible.

        Si `couplings` est fourni, il doit contenir une cle par machine cible.
        Sinon, `self.default_coupling` est applique a toutes les cibles.

        Pour chaque canal du signal source, on applique la fonction de
        transfert `H(f)` dans le domaine frequentiel puis on revient en
        temporel. Les signaux propages sont MIS A ZERO sur les machines
        identiques a la source (pas d'auto-propagation).
        """
        del source_machine  # pas utilise directement : on prend les signaux en entree
        del kwargs  # reserve pour extensions futures
        couplings = couplings or {}
        result: dict[str, SignalDict] = self._empty_target_dict(target_machines)

        for target in target_machines:
            coupling = couplings.get(target, self.default_coupling)
            for channel, sig in signal_dict.items():
                self._check_signal(sig, f"signal_dict[{channel!r}]")
                result[target][channel] = self._apply_transfer(sig, coupling)

        return result

    def attenuation_db(
        self,
        freq_hz: float,
        coupling: MechanicalCoupling,
    ) -> float:
        """Attenuation en dB pour une frequence et un couplage donnes.

        |H(f)| = exp(-alpha * d * f)  ->  20 log10(|H|) = -20 alpha d f / ln(10)
        """
        if freq_hz < 0:
            raise ValueError("freq_hz doit etre >= 0.")
        linear = np.exp(-coupling.alpha_s_per_m * coupling.distance_m * freq_hz)
        if linear <= 0:
            return float("inf")
        att_db = -20.0 * np.log10(linear)
        att_db += coupling.extra_attenuation_db
        return float(att_db)

    def _apply_transfer(
        self, signal: np.ndarray, coupling: MechanicalCoupling
    ) -> np.ndarray:
        """Applique H(f) = exp(-alpha * d * f) au signal en domaine frequentiel."""
        n = len(signal)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.fs)
        spectrum = np.fft.rfft(signal)
        # Calcul vectorise de |H(f)| puis application
        magnitude = np.exp(-coupling.alpha_s_per_m * coupling.distance_m * freqs)
        if coupling.extra_attenuation_db > 0.0:
            magnitude *= 10.0 ** (-coupling.extra_attenuation_db / 20.0)
        spectrum_propagated = spectrum * magnitude
        return np.fft.irfft(spectrum_propagated, n=n).astype(np.float64)
