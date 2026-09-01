"""Orchestrateur Discrete Event Simulation (DES) — Factory Twin Phase A.

Squelette minimal de la chaîne de production de l'usine simulée Phase A
(5 machines + buffers + source + sink), basé sur SimPy 4.x.

**Statut (2026-09-01) :** SQUELETTE — la topologie et l'API sont
posées, mais aucune simulation réelle n'est exécutée. Les durées
opératoires sont à 0.0, les taux de panne à 0.0. L'implémentation
complète (processus machine, propagation P1 production, dashboards)
arrive en SA2-SA7 du CDC.

**Sources :**
- SimPy 4.x : `https://gitlab.com/team-simit/simpy/`
- FactorySimPy (alternative plus haut-niveau) : `https://github.com/FactorySimPy/FactorySimPy`
  (non retenue pour Phase A — SimPy direct suffit pour 5 machines)
- CDC §3.1 : 5 machines Phase A, 1 moto-réducteur, 3 propagations actives (P1, P2, P3)

**Discipline "0 mock" :**
- Aucune valeur de durée ou de taux n'est codée en dur. Les durées
  seront chargées depuis `configs/usine_phase_a.yaml` (à enrichir).
- Les durées à 0.0 sont des **valeurs explicites non-calibrées**, pas
  des mocks silencieux : une `Duration` avec `confidence="uncalibrated"`
  est levée comme `ValueError` si on tente de l'utiliser dans un
  `simulate()` effectif (à implémenter en SA2).

**Conventions :**
- Tous les `Process` SimPy sont des générateurs (`yield`).
- Tous les `Container` représentent des buffers capacitifs.
- Tous les noms d'objets sont en anglais (cohérent avec SimPy).
- Toutes les docstrings sont en français.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import simpy
import yaml

# ---------------------------------------------------------------------------
# Constantes de topologie Phase A
# ---------------------------------------------------------------------------

# Numéros canoniques des 5 machines Phase A (CDC §3.1) :
#   M1 → M2 → M3 → M4 → M5
# Séquence de flux : moteur → réducteur → convoyeur → presse → pompe.
PHASE_A_MACHINES: tuple[str, ...] = ("M1", "M2", "M3", "M4", "M5")

# Mapping machine_id → label lisible (utilisé dans les logs, dashboards).
PHASE_A_MACHINE_LABELS: dict[str, str] = {
    "M1": "Moteur asynchrone 75 kW VFD",
    "M2": "Pompe hydraulique",
    "M3": "Réducteur hélicoïdal 2 étages",
    "M4": "Convoyeur bande 50 m",
    "M5": "Presse mécanique 100 T",
}


# ---------------------------------------------------------------------------
# Structure de configuration du modèle (hydratée depuis YAML)
# ---------------------------------------------------------------------------

@dataclass
class MachineSpec:
    """Spécification d'une machine pour la simulation DES.

    Attributs :
        machine_id : identifiant canonique (`M1`..`M5`).
        label : nom lisible humain.
        cycle_time_s : durée nominale d'un cycle (production d'une
            unité). **Non calibré en Phase A** (0.0, à charger depuis
            `configs/usine_phase_a.yaml` quand enrichi).
        buffer_capacity : capacité du buffer en amont (0 = aucun
            buffer, blocage immédiat en cas de machine aval occupée).
        mtbf_h : Mean Time Between Failures en heures (0 = pas de
            panne simulée). **Non calibré en Phase A.**
    """

    machine_id: str
    label: str
    cycle_time_s: float = 0.0
    buffer_capacity: int = 0
    mtbf_h: float = 0.0
    confidence: str = "uncalibrated"
    source_citation: str = ""


@dataclass
class PhaseAFactoryConfig:
    """Configuration complète chargée depuis `configs/usine_phase_a.yaml`.

    Attributs :
        machines : dictionnaire `machine_id -> MachineSpec` pour les
            5 machines Phase A.
        simulation_horizon_s : horizon de simulation en secondes
            (par défaut 8h = 1 shift, valeur à valider).
        warmup_s : temps de chauffe initial (durée avant laquelle les
            statistiques ne sont pas comptées) — 0 par défaut.
        source_path : chemin du fichier YAML source, conservé pour
            traçabilité (règle "0 mock" : provenance documentée).
    """

    machines: dict[str, MachineSpec] = field(default_factory=dict)
    simulation_horizon_s: float = 8 * 3600.0
    warmup_s: float = 0.0
    source_path: str = ""


def load_config(config_path: str | Path) -> PhaseAFactoryConfig:
    """Charge la configuration depuis un fichier YAML.

    Le fichier YAML doit définir une section `phase_a_factory` avec
    les sous-clés `simulation_horizon_s`, `warmup_s` et `machines`.
    Chaque machine est une entrée `M1: {...}`, `M2: {...}`, etc.

    Les champs non-renseignés restent aux valeurs par défaut
    (cycle_time_s=0.0, confidence="uncalibrated") et le module
    refusera de lancer une simulation effective avec ces valeurs
    tant qu'elles n'auront pas été calibrées.

    Lève :
        FileNotFoundError : si `config_path` n'existe pas.
        ValueError : si la structure YAML est invalide (machine_id
            absent, doublon, machine non listée dans
            `PHASE_A_MACHINES`).
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config Phase A introuvable : {path.resolve()}"
        )
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "phase_a_factory" not in raw:
        raise ValueError(
            f"Config Phase A {path!s} : cle racine 'phase_a_factory' absente"
        )
    section = raw["phase_a_factory"]
    if not isinstance(section, dict):
        raise ValueError(
            f"Config Phase A {path!s} : 'phase_a_factory' doit etre un mapping"
        )
    machines_raw = section.get("machines", {})
    if not isinstance(machines_raw, dict):
        raise ValueError(
            f"Config Phase A {path!s} : 'machines' doit etre un mapping"
        )

    cfg = PhaseAFactoryConfig(
        simulation_horizon_s=float(section.get("simulation_horizon_s", 8 * 3600.0)),
        warmup_s=float(section.get("warmup_s", 0.0)),
        source_path=str(path.resolve()),
    )
    for machine_id in PHASE_A_MACHINES:
        if machine_id not in machines_raw:
            # Non-bloquant : la machine peut etre ajoutee ulterieurement.
            continue
        mspec_raw = machines_raw[machine_id]
        if not isinstance(mspec_raw, dict):
            raise ValueError(
                f"Config Phase A {path!s} : machine {machine_id!r} "
                "doit etre un mapping"
            )
        cfg.machines[machine_id] = MachineSpec(
            machine_id=machine_id,
            label=str(mspec_raw.get("label", PHASE_A_MACHINE_LABELS[machine_id])),
            cycle_time_s=float(mspec_raw.get("cycle_time_s", 0.0)),
            buffer_capacity=int(mspec_raw.get("buffer_capacity", 0)),
            mtbf_h=float(mspec_raw.get("mtbf_h", 0.0)),
            confidence=str(mspec_raw.get("confidence", "uncalibrated")),
            source_citation=str(mspec_raw.get("source_citation", "")),
        )
    return cfg


# ---------------------------------------------------------------------------
# Topologie Phase A
# ---------------------------------------------------------------------------

def build_topology(env: simpy.Environment, cfg: PhaseAFactoryConfig) -> dict[str, Any]:
    """Construit la topologie de la chaîne Phase A dans l'environnement SimPy.

    Topologie :
        source → M1 → buffer1 → M2 → buffer2 → M3 → buffer3 → M4 → buffer4
        → M5 → sink

    Les 5 machines sont positionnées dans l'ordre canonique
    `PHASE_A_MACHINES`. Chaque `M_n` (sauf M1) est précédée d'un
    buffer (Container SimPy) de capacité `MachineSpec.buffer_capacity`.

    **Statut squelette :** les durées de cycle et les pannes ne sont
    pas encore câblées (cycle_time_s=0.0 dans la config par défaut).
    Le but est de poser l'infrastructure DES pour les sessions SA2+.

    Retourne un dictionnaire avec les références (utile pour tests et
    instrumentation ultérieure) :
        - `buffers` : dict `f"M{n}_in" -> simpy.Container`
        - `machines` : dict `f"M{n}" -> dict` (placeholder, valeur `None`
          en squelette — la classe Machine sera ajoutée en SA2)
        - `source` : place-holder pour la source de pièces
        - `sink` : place-holder pour le puits de sortie
    """
    buffers: dict[str, simpy.Container] = {}
    for machine_id in PHASE_A_MACHINES[1:]:  # M2..M5
        spec = cfg.machines.get(machine_id)
        cap = spec.buffer_capacity if spec is not None else 0
        buffers[f"{machine_id}_in"] = simpy.Container(env, capacity=cap)

    topology: dict[str, Any] = {
        "env": env,
        "buffers": buffers,
        "machines": {mid: None for mid in PHASE_A_MACHINES},
        "source": None,
        "sink": None,
        "config": cfg,
    }
    return topology


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def simulate(
    config_path: str | Path,
    until_s: float | None = None,
) -> dict[str, Any]:
    """Lance une simulation Phase A en squelette (aucune production réelle).

    Comportement :
        1. Charge la config depuis `config_path`.
        2. Crée un `simpy.Environment()`.
        3. Construit la topologie.
        4. Exécute `env.run(until=until_s)`.
        5. Retourne un résumé (topologie, horloge finale, source path).

    En l'état (squelette), aucune machine ne consomme de temps et
    aucun produit n'est généré. Le résultat de `env.run()` est donc
    déterministe et purement structurel : utile pour valider
    l'infrastructure (tests d'import, vérification de topologie).

    Lève :
        ValueError : si la config est incomplète au point d'empêcher
            un run structurel (par ex. : cycle_time_s > 0 mais
            confidence=uncalibrated — on refuse de produire des
            métriques non-calibrées). En squelette Phase A, ce
            verrou n'est **pas** déclenché tant que les valeurs
            restent à 0.0.
    """
    cfg = load_config(config_path)
    horizon = until_s if until_s is not None else cfg.simulation_horizon_s

    env = simpy.Environment()
    topology = build_topology(env, cfg)
    env.run(until=horizon)

    return {
        "config_source": cfg.source_path,
        "horizon_s": horizon,
        "warmup_s": cfg.warmup_s,
        "machines_configured": sorted(cfg.machines.keys()),
        "buffers_built": sorted(topology["buffers"].keys()),
        "final_clock_s": float(env.now),
        "status": "squelette" if all(
            cfg.machines[mid].cycle_time_s == 0.0
            for mid in PHASE_A_MACHINES
            if mid in cfg.machines
        ) else "configured",
    }


__all__ = [
    "PHASE_A_MACHINES",
    "PHASE_A_MACHINE_LABELS",
    "MachineSpec",
    "PhaseAFactoryConfig",
    "build_topology",
    "load_config",
    "simulate",
]
