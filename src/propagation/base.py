"""Interface abstraite des propagateurs de defauts multi-machines (Factory Twin Phase A).

Un propagateur prend en entree un signal defectueux (vibration, courant, etc.)
genere par une machine source et retourne sa contribution sur chaque machine
cible (attenuee, filtree, retardee selon la physique du mode de propagation).

Trois propagations concretes implementees (cf. `docs/CDC_projet.md` §3.1, D7) :
    - P1 Production (DES, pas dans ce module)
    - P2 Mecanique   -> `src.propagation.mechanical.MechanicalPropagator`
    - P3 Electrique  -> `src.propagation.electrical.ElectricalPropagator`

P4 Thermique est un squelette Phase A (active Phase B), pas dans ce module.

Conventions :
    - Les signaux sont representes par `dict[str, np.ndarray]` (cles = types
      de signaux, ex. 'vibration', 'current'). Cela permet a un meme
      propagateur de traiter simultanement plusieurs grandeurs physiques.
    - La methode `propagate(...)` est PURE : elle n'a pas d'effet de bord
      sur la source. Elle retourne un dict par machine cible :
        {machine_id: signal_contribue}
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

# Type alias pour un signal multi-canaux
SignalDict = dict[str, np.ndarray]


class Propagator(ABC):
    """Interface abstraite d'un propagateur de defauts."""

    @abstractmethod
    def propagate(
        self,
        signal_dict: SignalDict,
        source_machine: str,
        target_machines: list[str],
        **kwargs: Any,
    ) -> dict[str, SignalDict]:
        """Propage un signal defectueux d'une machine source vers N machines cibles.

        Parametres
        ----------
        signal_dict : SignalDict
            Signaux bruts generes par la machine source (par canal).
        source_machine : str
            Identifiant de la machine source (ex. 'M1_motor_vfd').
        target_machines : list[str]
            Identifiants des machines cibles.
        **kwargs
            Arguments specifiques au type de propagation (ex. distances
            geometriques pour la propagation mecanique, impédances reseau
            pour la propagation electrique).

        Retour
        ------
        dict[str, SignalDict]
            Pour chaque machine cible, le signal propage (attenue, filtre,
            eventuellement decale) par canal. Une machine source peut
            apparaitre dans `target_machines` (auto-propagation, ignoree).
        """
        raise NotImplementedError

    @staticmethod
    def _empty_target_dict(target_machines: list[str]) -> dict[str, SignalDict]:
        """Construit la structure de sortie vide pour les machines cibles."""
        return {m: {} for m in target_machines}

    @staticmethod
    def _check_signal(signal: np.ndarray, name: str) -> None:
        """Verifie la forme d'un signal 1D numpy."""
        if not isinstance(signal, np.ndarray):
            raise TypeError(f"{name} doit etre un np.ndarray, recu {type(signal)}.")
        if signal.ndim != 1:
            raise ValueError(f"{name} doit etre 1D, recu shape={signal.shape}.")
        if signal.size == 0:
            raise ValueError(f"{name} est vide.")
