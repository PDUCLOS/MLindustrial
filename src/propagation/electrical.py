"""Propagation P3 - harmoniques secteur via bus electrique partage (Factory Twin Phase A).

Modele physique :
    Un moteur alimente par variateur de frequence (VFD) genere des harmoniques
    de courant (H3, H5, H7 dominants) qui se propagent sur le bus electrique
    partage. La modelisation simplifiee (phase A) utilise un diviseur
    d'impedance entre l'impedance du bus (Zbus) et l'impedance de la charge
    (Zcharge) :

        Vh = Vh_nominal * 1 / (1 + (Zbus/Zcharge) * h^2)

    Cette formulation est une approximation classique d'un reseau radial avec
    une source d'harmoniques non-lineaire en parallele (voir Arrillaga &
    Watson, "Power System Harmonics", Wiley). Le facteur h^2 traduit l'effet
    de la frequence sur l'impedance inductive du bus (Zbus ~ j*L*w, donc
    |Zbus| ~ h pour une inductance pure ; combine avec une charge capacitive
    ou resistive, l'attenuation croît en h^2 dans le cas typique).

    Plus le rapport Zbus/Zcharge est :
        - eleve : bus "faible" (forte impedance de source), harmoniques tres
                  attenuées -> couplage faible entre machines
        - faible : bus "puissant" (faible impedance de source), harmoniques
                   peu attenuées -> couplage fort entre machines

References :
    - `docs/theorie_reference.md` §4 (MCSA et harmoniques secteur)
    - `docs/CDC_projet.md` §3.1 P3 (propagation electrique)
    - Arrillaga J., Watson N.R., "Power System Harmonics", Wiley 2003
    - IEC 61000-2-2 (niveaux de compatibilite pour les harmoniques secteur)

Critere de validation Phase A (CDC §7.1 A5) : VFD M1 -> harmoniques 50 Hz
visibles sur M2-M5 avec attenuation H3 > H5 > H7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .base import Propagator, SignalDict

# Constantes physiques (confirmed) :
# - Frequence secteur EU : 50 Hz (norme IEC 60038)
# - Harmoniques VFD dominants : H3, H5, H7 (theorie des redresseurs 6 pulses,
#   voir Arrillaga & Watson 2003)
MAINS_HZ = 50.0
VFD_HARMONIC_RANKS = (3, 5, 7)


@dataclass(frozen=True)
class ElectricalBusCoupling:
    """Couplage par bus electrique entre machines.

    Le rapport `zbus_over_zcharge` controle l'attenuation : 0 = couplage
    parfait (bus infiniment puissant), +inf = aucune propagation.
    """

    zbus_over_zcharge: float
    mains_hz: float = MAINS_HZ


class ElectricalPropagator(Propagator):
    """Propagation P3 - harmoniques secteur sur bus partage.

    Parametres
    ----------
    fs : int
        Frequence d'echantillonnage des signaux courant (Hz).
    default_coupling : ElectricalBusCoupling
        Couplage par defaut utilise si `propagate(...)` n'en precise pas.
    harmonic_ranks : tuple[int, ...]
        Rangs d'harmoniques VFD modelises (defaut H3/H5/H7).
    """

    def __init__(
        self,
        fs: int = 64000,
        default_coupling: ElectricalBusCoupling | None = None,
        harmonic_ranks: tuple[int, ...] = VFD_HARMONIC_RANKS,
    ) -> None:
        if fs <= 0:
            raise ValueError("fs doit etre strictement positif.")
        for h in harmonic_ranks:
            if h < 1:
                raise ValueError(f"harmonic_ranks doit etre >= 1, recu h={h}.")
        self.fs = fs
        self.default_coupling = default_coupling or ElectricalBusCoupling(
            zbus_over_zcharge=0.1,  # 0.1 = bus "puissant", couplage eleve
        )
        self.harmonic_ranks = tuple(harmonic_ranks)

    def propagate(
        self,
        signal_dict: SignalDict,
        source_machine: str,
        target_machines: list[str],
        couplings: dict[str, ElectricalBusCoupling] | None = None,
        **kwargs: Any,
    ) -> dict[str, SignalDict]:
        """Propage le canal `current` d'une machine source vers les cibles.

        Seul le canal `current` est propage (les harmoniques electriques
        n'affectent pas la vibration mecanique). Pour les autres canaux, le
        resultat est un tableau de zeros (place-holder explicite pour debug).

        Si `couplings` est fourni, il doit contenir une cle par machine cible.
        Sinon, `self.default_coupling` est applique.
        """
        del source_machine
        del kwargs
        couplings = couplings or {}
        result: dict[str, SignalDict] = self._empty_target_dict(target_machines)
        current_signal = signal_dict.get("current")
        if current_signal is None:
            # Pas de signal courant a propager : on retourne des zeros partout
            for target in target_machines:
                for channel in signal_dict.keys():
                    result[target][channel] = np.zeros_like(
                        np.array(signal_dict[channel], dtype=np.float64)
                    )
            return result

        self._check_signal(current_signal, "signal_dict['current']")
        n = len(current_signal)
        harmonic_freqs = np.array(
            [h * self.default_coupling.mains_hz for h in self.harmonic_ranks],
            dtype=np.float64,
        )

        for target in target_machines:
            coupling = couplings.get(target, self.default_coupling)
            att_factors = self._harmonic_attenuation(coupling, harmonic_freqs)
            target_current = np.zeros(n, dtype=np.float64)
            current_spectrum = np.fft.rfft(current_signal)
            freqs = np.fft.rfftfreq(n, d=1.0 / self.fs)
            for harmonic_freq, att in zip(harmonic_freqs, att_factors, strict=True):
                # Index de la raie harmonique dans le spectre FFT
                idx = int(np.argmin(np.abs(freqs - harmonic_freq)))
                # VFD injecte une raie a +/- 2 bins autour de la frequence nominale
                # (largeur typique due au bruit de modulation du redresseur).
                for k in (idx - 2, idx - 1, idx, idx + 1, idx + 2):
                    if 0 <= k < len(current_spectrum):
                        current_spectrum[k] *= att
            target_current = np.fft.irfft(current_spectrum, n=n).astype(np.float64)
            result[target]["current"] = target_current
            # Place-holder explicite : les autres canaux ne sont pas propages
            for channel in signal_dict.keys():
                if channel != "current":
                    result[target][channel] = np.zeros(
                        len(signal_dict[channel]), dtype=np.float64
                    )
        return result

    def _harmonic_attenuation(
        self,
        coupling: ElectricalBusCoupling,
        harmonic_freqs: np.ndarray,
    ) -> np.ndarray:
        """Calcule le facteur multiplicatif d'amplitude pour chaque harmonique.

        Formule : Vh / Vh_nominal = 1 / (1 + (Zbus/Zcharge) * h^2)

        Retourne un facteur dans [0, 1].
        """
        if coupling.zbus_over_zcharge < 0:
            raise ValueError("zbus_over_zcharge doit etre >= 0.")
        ranks = harmonic_freqs / coupling.mains_hz
        return 1.0 / (1.0 + coupling.zbus_over_zcharge * ranks ** 2)

    def attenuation_db(
        self,
        harmonic_rank: int,
        coupling: ElectricalBusCoupling | None = None,
    ) -> float:
        """Attenuation en dB pour un rang d'harmonique donne.

        Utile pour les tests et le diagnostic.
        """
        coupling = coupling or self.default_coupling
        if harmonic_rank < 1:
            raise ValueError("harmonic_rank doit etre >= 1.")
        factor = 1.0 / (1.0 + coupling.zbus_over_zcharge * harmonic_rank ** 2)
        if factor <= 0:
            return float("inf")
        return float(-20.0 * np.log10(factor))
