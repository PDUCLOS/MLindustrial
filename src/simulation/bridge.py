"""Bridge DES (SimPy) <-> signaux physiques (Factory Twin Phase A).

Role :
    Faire le lien entre les evenements Discrete Event Simulation (machine_start,
    machine_stop, defect_onset) et la generation/mise a jour des signaux
    physiques par machine, puis appliquer les propagations inter-machines
    (P2 mecanique, P3 electrique).

    Le bridge est agnostique du moteur DES utilise : il consomme des `DESEvent`
    (dataclass Python) qui peuvent etre emis par SimPy (via un `process` qui
    yield l'evenement), par FactorySimPy, ou directement par du code de test.
    Cette separation permet de tester le pont SANS monter une simulation
    complete (cf. `tests/test_bridge.py`).

Cycle d'utilisation :
    1. A l'init, on enregistre :
        - une `simulator_fn` par machine (callable qui produit un signal dict)
        - une liste de propagateurs (P2, P3)
    2. On pousse les evenements DES au fil de l'eau via `handle_event()`.
    3. A chaque pas de simulation, on appelle `generate_signals(t, ...)` qui :
        - demande a chaque simulateur de machine de regenerer son signal
        - met a zero la vibration des machines arretees
        - applique les propagations sur les autres machines
    4. Le dashboard / la DB lit les signaux finaux via `get_signal()` ou
        `get_all_signals()`.

Conventions :
    - Le simulateur DOIT retourner un dict {canal: np.ndarray} (memes canaux
      pour toutes les machines du meme simulateur). Si le simulateur ne
      fournit pas un canal donne, le bridge considere ce canal comme absent.
    - Quand une machine est arretee (apres `machine_stop`), le bridge met sa
      vibration a zero MAIS preserve son signal courant pour permettre la
      propagation electrique P3 (cf. CDC §7.1 A5 : un VFD peut rester sous
      tension avec un rotor bloque - cas reel des defauts rotor locke).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from src.gearbox.helical import HelicalDefectConfig
from src.propagation.base import Propagator, SignalDict

# Type alias pour la fonction de simulation d'une machine
# Signature : (machine_id, is_running, defect_config, **kwargs) -> SignalDict
SimulatorFn = Callable[..., SignalDict]

# Types d'evenements DES supportes
DESEventType = Literal["machine_start", "machine_stop", "defect_onset"]


# ---------------------------------------------------------------------------
# Structures de donnees
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DESEvent:
    """Evenement Discrete Event Simulation.

    `payload` transporte les arguments optionnels (ex. nouveau defect_config
    pour un defect_onset). Le bridge ne lit que les champs qui le concernent.
    """

    event_type: DESEventType
    machine_id: str
    timestamp_s: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class _MachineRuntimeState:
    """Etat interne d'une machine dans le bridge (non expose)."""

    is_running: bool = True
    defect_config: HelicalDefectConfig = field(default_factory=HelicalDefectConfig)
    # Dernier signal genere, post-procede (vibration mise a zero si arretee).
    # None tant qu'aucun signal n'a ete demande.
    signal: SignalDict | None = None


# ---------------------------------------------------------------------------
# Bridge DES <-> physique
# ---------------------------------------------------------------------------


class SimulationBridge:
    """Pont entre les evenements DES et la generation des signaux physiques.

    Parametres
    ----------
    simulators : dict[str, SimulatorFn]
        Mapping `machine_id` -> fonction de simulation. Chaque fonction
        recoit (machine_id, is_running, defect_config, **kwargs) et retourne
        un `SignalDict` brut.
    propagators : list[Propagator]
        Liste des propagateurs a appliquer (P2, P3). L'ordre est preserve
        mais les propagations sont concues pour etre commutatives sur les
        canaux distincts (mecanique vs electrique).
    fs : int
        Frequence d'echantillonnage de reference (Hz). Les simulateurs
        doivent l'utiliser pour generer leurs signaux.
    """

    def __init__(
        self,
        simulators: dict[str, SimulatorFn],
        propagators: list[Propagator] | None = None,
        fs: int = 64000,
    ) -> None:
        if not simulators:
            raise ValueError("Au moins un simulateur de machine est requis.")
        if fs <= 0:
            raise ValueError("fs doit etre strictement positif.")
        self.simulators: dict[str, SimulatorFn] = dict(simulators)
        self.propagators: list[Propagator] = list(propagators or [])
        self.fs = fs
        self._states: dict[str, _MachineRuntimeState] = {
            mid: _MachineRuntimeState() for mid in simulators
        }

    # ------------------------------------------------------------------
    # API publique : gestion des evenements
    # ------------------------------------------------------------------

    def handle_event(self, event: DESEvent) -> None:
        """Traite un evenement DES (machine_start, machine_stop, defect_onset).

        Pour `machine_start` / `machine_stop` : bascule l'etat `is_running`.
        Pour `defect_onset` : recupere un `HelicalDefectConfig` dans le payload
        et le stocke comme defaut courant de la machine.
        """
        state = self._states.get(event.machine_id)
        if state is None:
            raise KeyError(
                f"Machine inconnue dans le bridge : {event.machine_id!r}. "
                f"Machines enregistrees : {sorted(self._states.keys())}."
            )
        if event.event_type == "machine_start":
            state.is_running = True
        elif event.event_type == "machine_stop":
            state.is_running = False
        elif event.event_type == "defect_onset":
            new_defect = event.payload.get("defect_config")
            if not isinstance(new_defect, HelicalDefectConfig):
                raise TypeError(
                    "defect_onset attend un payload {'defect_config': HelicalDefectConfig}, "
                    f"recu payload={event.payload!r}."
                )
            state.defect_config = new_defect
        else:
            raise ValueError(f"Type d'evenement DES inconnu : {event.event_type!r}.")

    # ------------------------------------------------------------------
    # API publique : generation des signaux et lecture
    # ------------------------------------------------------------------

    def generate_signals(
        self,
        duration_s: float = 4.0,
        **sim_kwargs: Any,
    ) -> dict[str, SignalDict]:
        """Regenere les signaux de toutes les machines et applique les propagations.

        Pour chaque machine :
        1. Appelle le simulateur avec (machine_id, is_running, defect_config).
        2. Met a zero la vibration si la machine est arretee.
        3. Stocke le signal comme "courant" pour cette machine.

        Pour chaque propagateur, applique la propagation sur les autres machines.

        Retourne un dict {machine_id: SignalDict_final} avec les signaux
        effectivement presents sur chaque machine (source + contributions
        propagees).
        """
        if duration_s <= 0:
            raise ValueError("duration_s doit etre > 0.")
        # 1. Generation brute par machine
        for machine_id, state in self._states.items():
            sim = self.simulators[machine_id]
            raw_signal: SignalDict = sim(
                machine_id,
                state.is_running,
                state.defect_config,
                duration_s=duration_s,
                fs=self.fs,
                **sim_kwargs,
            )
            # 2. Post-traitement : si la machine est arretee, on force la
            # vibration a zero mais on preserve le courant (le VFD peut rester
            # sous tension avec un rotor bloque - cas reel des defauts rotor
            # locke, documente dans CDC §7.1 A5).
            processed = self._post_process_stopped_machine(raw_signal, state.is_running)
            state.signal = processed

        # 3. Aggregation : on part d'une copie des signaux sources, puis on
        # ajoute les contributions propagees.
        aggregated: dict[str, SignalDict] = {
            mid: dict(state.signal) if state.signal else {}
            for mid, state in self._states.items()
        }

        for propagator in self.propagators:
            for source_id, source_state in self._states.items():
                if not source_state.signal:
                    continue
                target_ids = [
                    mid for mid in self._states.keys() if mid != source_id
                ]
                if not target_ids:
                    continue
                contributions = propagator.propagate(
                    signal_dict=source_state.signal,
                    source_machine=source_id,
                    target_machines=target_ids,
                )
                for target_id, contrib_signal in contributions.items():
                    for channel, sig in contrib_signal.items():
                        if target_id not in aggregated:
                            aggregated[target_id] = {}
                        if channel in aggregated[target_id]:
                            aggregated[target_id][channel] = (
                                aggregated[target_id][channel] + sig
                            )
                        else:
                            aggregated[target_id][channel] = sig
        return aggregated

    def get_signal(self, machine_id: str, channel: str | None = None) -> SignalDict | np.ndarray | None:
        """Acces au dernier signal genere pour une machine.

        Si `channel` est precise, retourne le np.ndarray du canal (ou None).
        Sinon retourne le SignalDict complet (ou None).
        """
        state = self._states.get(machine_id)
        if state is None or state.signal is None:
            return None
        if channel is None:
            return dict(state.signal)
        return state.signal.get(channel)

    def get_all_signals(self) -> dict[str, SignalDict]:
        """Acces aux derniers signaux generes pour toutes les machines."""
        return {
            mid: dict(state.signal) if state.signal else {}
            for mid, state in self._states.items()
        }

    def is_running(self, machine_id: str) -> bool:
        """Etat courant de marche d'une machine."""
        state = self._states.get(machine_id)
        if state is None:
            raise KeyError(f"Machine inconnue : {machine_id!r}.")
        return state.is_running

    def get_defect_config(self, machine_id: str) -> HelicalDefectConfig:
        """Defaut courant d'une machine."""
        state = self._states.get(machine_id)
        if state is None:
            raise KeyError(f"Machine inconnue : {machine_id!r}.")
        return state.defect_config

    # ------------------------------------------------------------------
    # Methodes privees
    # ------------------------------------------------------------------

    @staticmethod
    def _post_process_stopped_machine(
        signal: SignalDict,
        is_running: bool,
    ) -> SignalDict:
        """Force la vibration a zero si la machine est arretee.

        Le canal `current` est preserve (cas VFD sous tension avec rotor
        bloque). Si un autre canal est present, on le preserve tel quel.
        """
        if is_running:
            return {k: v.copy() for k, v in signal.items()}
        processed: SignalDict = {}
        for channel, sig in signal.items():
            copied = np.array(sig, dtype=np.float64).copy()
            if channel == "vibration":
                copied.fill(0.0)
            processed[channel] = copied
        return processed
