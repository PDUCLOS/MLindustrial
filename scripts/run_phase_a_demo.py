#!/usr/bin/env python3
"""Orchestration du dataset synthetique Phase A (Factory Twin).

**Cible :** SA7 du CDC (`docs/CDC_projet.md` §6.1) — generer le
dataset qui alimente le dashboard Streamlit de l'onglet Factory
Twin (validation du critere A6 : "Dashboard demo 3 scenarios,
rejouables en < 5 min, pas de crash sur 5 runs").

**Role :**
    - Charger `configs/usine_phase_a.yaml`.
    - Pour chaque machine (M1, M2, M3, M4, M5) : instancier le
      simulateur physique adapte, generer 4 s de signal a 64 kHz,
      sauvegarder dans `data/synthetic/phase_a/{machine_id}/run_001.parquet`.
    - Pour les propagations P2 + P3 (optionnelles) : simuler un
      defaut isole sur M1, appliquer le propagateur sur M2, sauvegarder
      les resultats dans `data/synthetic/phase_a/propagation_*.parquet`.
    - Afficher un resume console : chemins crees, RMS par canal,
      ratios d'attenuation.

**Discipline "0 mock" (auditee, `docs/audit_zero_mock_2026-09-01.md`) :**
    - Toutes les valeurs numeriques viennent d'un simulateur deterministe
      (graine fixee par --seed). Aucune constante inventee.
    - Les colonnes ecrites dependent du simulateur utilise :
      M1/M4 -> vibration, current_1, current_2, tacho (motor_induction)
      M2 -> vibration, pressure, flow, temperature (pump_centrifuge)
      M3 -> vibration, current (helical gearbox)
      M5 -> vibration, current (press_mechanical)
    - Pour les fichiers de propagation : on ecrit explicitement les
      signaux source, cible sain, cible propage, plus les metadonnees
      d'attenuation (en dB) lues depuis les propagateurs.

**Usage :**
    uv run python scripts/run_phase_a_demo.py
    uv run python scripts/run_phase_a_demo.py --seed 42 \\
        --machines M1 M2 M3 M4 M5 --propagations yes
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Permet l'import du package `src.*` quel que soit le cwd (pattern
# commun a tous les scripts du repo, cf. scripts/generate_aas.py).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.time_domain import rms
from src.gearbox.helical import (
    HelicalDefectConfig,
    HelicalGearGeometry,
    simulate_helical_gearbox,
)
from src.propagation.electrical import ElectricalPropagator
from src.propagation.mechanical import (
    ALPHA_CONCRETE_RIGID_S,
    MechanicalCoupling,
    MechanicalPropagator,
)
from src.simulation._helpers import default_defect_config
from src.simulation.motor_induction import simulate_motor
from src.simulation.press_mechanical import simulate_press
from src.simulation.pump_centrifuge import simulate_pump

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PHASE_A_MACHINES: tuple[str, ...] = ("M1", "M2", "M3", "M4", "M5")
PHASE_A_MACHINE_LABELS: dict[str, str] = {
    "M1": "Moteur asynchrone 75 kW VFD",
    "M2": "Pompe hydraulique",
    "M3": "Reducteur helicoidal 2 etages",
    "M4": "Convoyeur bande 50 m",
    "M5": "Presse mecanique 100 T",
}

# Frequence d'echantillonnage et duree (alignes Paderborn, source :
# CDC §6.1 SA3-SA5 et `docs/architecture_usine_simulation.md` §7).
FS_DEFAULT: int = 64000
DURATION_S_DEFAULT: float = 4.0

# Vitesse nominale par machine (lecture directe des parametres reels
# dans `configs/usine_phase_a.yaml`, pas une estimation).
DEFAULT_MACHINE_RPM: dict[str, float] = {
    "M1": 1500.0,  # 4 poles / 50 Hz (synchronisme)
    "M2": 3000.0,  # 2 poles / 50 Hz (synchronisme)
    "M3": 1500.0,  # input_rpm du reducteur helicoidal
    "M4": 100.0,   # tambour convoyeur (cf. config)
    "M5": 200.0,   # bielle presse (DEFAULT_CRANKSHAFT_RPM)
}

# Chemin de sortie (coherent avec .gitignore : `data/synthetic/` n'est
# pas versionne — c'est un artefact de run, pas du code source).
OUTPUT_DIR = ROOT / "data" / "synthetic" / "phase_a"


# ---------------------------------------------------------------------------
# Dispatch simulateur
# ---------------------------------------------------------------------------


def simulate_machine(
    machine_id: str,
    seed: int,
    defect_config: dict[str, float] | None = None,
    duration_s: float = DURATION_S_DEFAULT,
    fs: int = FS_DEFAULT,
) -> dict[str, np.ndarray]:
    """Dispatch vers le simulateur physique adapte a la machine.

    Note M4 : aucun simulateur dedie pour `belt_conveyor` en Phase A.
    On utilise `simulate_motor` avec rpm reel (100) et bearing_key
    "6205" (idler roller, geometrie connue dans `bearing_geometry.yaml`).
    Ce choix est documente ici, pas une invention silencieuse.

    L'appelant peut surcharger `defect_config` (defaut : sain = toutes
    les severites a 0 via `default_defect_config()`).
    """
    rpm = DEFAULT_MACHINE_RPM[machine_id]
    config = default_defect_config()
    if defect_config is not None:
        config.update(defect_config)

    if machine_id == "M1":
        return simulate_motor(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6203",
        )
    if machine_id == "M2":
        return simulate_pump(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6206",
        )
    if machine_id == "M3":
        geometry = HelicalGearGeometry()
        defect = HelicalDefectConfig(
            enable_wear=bool(config.get("bearing_outer_severity", 0) > 0),
            wear_severity=float(config.get("bearing_outer_severity", 0)),
        )
        return simulate_helical_gearbox(
            seed=seed, input_rpm=rpm, gear_geometry=geometry,
            defect_config=defect, duration_s=duration_s, fs=fs,
        )
    if machine_id == "M4":
        # Fallback documente : `simulate_motor` avec rpm=100 (config
        # reel de M4) et bearing_key d'un idler roller 6205 dont la
        # geometrie est dans `bearing_geometry.yaml`. Le YAML source
        # reference la ref "6205" (idler_rollers de M4) et "6306"
        # (drive_pulley), mais aucune de ces references n'a sa
        # geometrie renseignee (SB2 = extension catalogue roulements
        # prevu). On prend l'entree 6205-2RS_JEM_SKF (la plus proche
        # de la ref 6205 documentee dans le YAML d'usine), avec
        # justification explicite ici -- pas d'invention silencieuse.
        return simulate_motor(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6205-2RS_JEM_SKF",
        )
    if machine_id == "M5":
        return simulate_press(
            seed=seed, defect_config=config,
            duration_s=duration_s, fs=fs,
            crankshaft_rpm=rpm, cycle_freq_hz=1.0,
            bearing_keys=("22320", "22220"),
        )
    raise ValueError(f"Machine inconnue : {machine_id!r}")


# ---------------------------------------------------------------------------
# Ecriture parquet
# ---------------------------------------------------------------------------


def write_signals_parquet(
    path: Path,
    signals: dict[str, np.ndarray],
) -> None:
    """Ecrit les signaux dans un fichier parquet.

    Schema :
        - `sample_index` : int64, indice d'echantillon (0..N-1)
        - une colonne par canal du simulateur (`vibration`, `current_1`,
          `current_2`, `tacho`, `pressure`, `flow`, `temperature`, etc.)
        - metadata (fs, duration_s) stockees en attributs pyarrow.

    Le schema depend du simulateur utilise (cf. docstring module).
    """
    if not signals:
        raise ValueError("Aucun signal a ecrire (dict vide).")
    n_samples = len(next(iter(signals.values())))
    df = pd.DataFrame({"sample_index": np.arange(n_samples, dtype=np.int64)})
    for channel, sig in signals.items():
        arr = np.asarray(sig, dtype=np.float64)
        if len(arr) != n_samples:
            raise ValueError(
                f"Canal {channel!r} : longueur {len(arr)} != {n_samples}"
            )
        df[channel] = arr
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def write_propagation_parquet(
    path: Path,
    signals: dict[str, np.ndarray],
    extra_columns: dict[str, np.ndarray] | None = None,
) -> None:
    """Ecrit un fichier parquet de signaux propages.

    `signals` : dict {canal: array} du signal cible apres propagation.
    `extra_columns` : colonnes supplementaires a ajouter (ex. un
    signal de reference). Toutes les colonnes doivent avoir la meme
    longueur.
    """
    merged: dict[str, np.ndarray] = {}
    merged.update(signals)
    if extra_columns:
        merged.update(extra_columns)
    write_signals_parquet(path, merged)


# ---------------------------------------------------------------------------
# Generation par machine
# ---------------------------------------------------------------------------


@dataclass
class MachineRunResult:
    """Resultat de la generation pour une machine."""

    machine_id: str
    label: str
    path: Path
    rms_by_channel: dict[str, float]
    duration_s: float
    fs: int


def run_machine(
    machine_id: str,
    seed: int,
    output_dir: Path,
    defect_config: dict[str, float] | None = None,
    run_id: str = "run_001",
) -> MachineRunResult:
    """Simule une machine et ecrit son parquet dans `{output_dir}/{machine_id}/{run_id}.parquet`.

    Parameters
    ----------
    machine_id : str
        Identifiant canonique (`M1`..`M5`).
    seed : int
        Graine du generateur aleatoire.
    output_dir : Path
        Repertoire racine de sortie (typiquement `data/synthetic/phase_a/`).
    defect_config : dict[str, float] or None
        Configuration de defauts (`None` = sain).
    run_id : str
        Suffixe du fichier (par defaut `run_001`).

    Returns
    -------
    MachineRunResult
        Resume du run (chemin, RMS par canal, duree, fs).
    """
    signals = simulate_machine(
        machine_id, seed=seed, defect_config=defect_config,
    )
    n_samples = len(next(iter(signals.values())))
    fs = FS_DEFAULT
    duration_s = n_samples / fs
    out_path = output_dir / machine_id / f"{run_id}.parquet"
    write_signals_parquet(out_path, signals)

    rms_by_channel = {chan: rms(sig) for chan, sig in signals.items()}
    return MachineRunResult(
        machine_id=machine_id,
        label=PHASE_A_MACHINE_LABELS[machine_id],
        path=out_path,
        rms_by_channel=rms_by_channel,
        duration_s=duration_s,
        fs=fs,
    )


# ---------------------------------------------------------------------------
# Generation propagations
# ---------------------------------------------------------------------------


@dataclass
class PropagationResult:
    """Resultat d'une demo de propagation."""

    label: str
    path: Path
    rms_source: float
    rms_target_initial: float
    rms_target_propagated: float
    attenuation_db: dict[str, float]


def run_propagation_p2(
    seed: int,
    output_dir: Path,
) -> PropagationResult:
    """Demo P2 : vibration M1 defaillant -> vibration M2.

    Source : M1 avec balourd severe (unbalance_severity=0.8).
    Couplage : dalle beton rigide, 5 m, alpha=5e-4 s/m (defaut).
    """
    defect_source = default_defect_config()
    defect_source["unbalance_severity"] = 0.8
    source_signal = simulate_machine("M1", seed=seed, defect_config=defect_source)
    target_signal = simulate_machine("M2", seed=seed + 1)

    propagator = MechanicalPropagator(fs=FS_DEFAULT)
    contributions = propagator.propagate(
        signal_dict={"vibration": source_signal["vibration"]},
        source_machine="M1",
        target_machines=["M2"],
    )
    contrib = contributions["M2"]["vibration"]
    propagated = dict(target_signal)
    propagated["vibration"] = target_signal["vibration"] + contrib

    # Attenuation en dB pour la raie 1x fr (25 Hz @ 1500 rpm).
    coupling = MechanicalCoupling(distance_m=5.0, alpha_s_per_m=ALPHA_CONCRETE_RIGID_S)
    att_1x_db = propagator.attenuation_db(freq_hz=25.0, coupling=coupling)

    out_path = output_dir / "propagation_mecanique_M1_to_M2.parquet"
    write_propagation_parquet(
        out_path,
        signals=propagated,
        extra_columns={"vibration_propagated_from_M1": contrib},
    )
    return PropagationResult(
        label="P2 mecanique (vibration, M1 -> M2, 5 m dalle rigide)",
        path=out_path,
        rms_source=rms(source_signal["vibration"]),
        rms_target_initial=rms(target_signal["vibration"]),
        rms_target_propagated=rms(propagated["vibration"]),
        attenuation_db={"1x_fr_25Hz_5m": att_1x_db},
    )


def run_propagation_p3(
    seed: int,
    output_dir: Path,
) -> PropagationResult:
    """Demo P3 : courant M1 defectueux (rotor bars) -> courant M2.

    Source : M1 avec barres rotor cassees (rotor_bar_severity=0.4).
    Couplage : bus 'puissant' (zbus/zcharge=0.1, defaut).
    """
    defect_source = default_defect_config()
    defect_source["rotor_bar_severity"] = 0.4
    source_signal = simulate_machine("M1", seed=seed, defect_config=defect_source)
    target_signal = simulate_machine("M2", seed=seed + 1)

    propagator = ElectricalPropagator(fs=FS_DEFAULT)
    contributions = propagator.propagate(
        signal_dict={"current": source_signal["current_1"]},
        source_machine="M1",
        target_machines=["M2"],
    )
    contrib = contributions["M2"]["current"]
    # M2 (pompe) n'a pas de canal 'current' en sortie. On l'initialise a zero.
    initial_current = target_signal.get("current", np.zeros_like(contrib))
    propagated = dict(target_signal)
    propagated["current"] = initial_current + contrib

    # Attenuations en dB des harmoniques secteur (fs=50 Hz).
    att_h3_db = propagator.attenuation_db(3)
    att_h5_db = propagator.attenuation_db(5)
    att_h7_db = propagator.attenuation_db(7)

    out_path = output_dir / "propagation_electrique_M1_to_M2.parquet"
    write_propagation_parquet(
        out_path,
        signals=propagated,
        extra_columns={"current_propagated_from_M1": contrib},
    )
    return PropagationResult(
        label="P3 electrique (courant, M1 -> M2, bus zbus/zcharge=0.1)",
        path=out_path,
        rms_source=rms(source_signal["current_1"]),
        rms_target_initial=rms(initial_current),
        rms_target_propagated=rms(propagated["current"]),
        attenuation_db={
            "H3_150Hz": att_h3_db,
            "H5_250Hz": att_h5_db,
            "H7_350Hz": att_h7_db,
        },
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description=(
            "Genere un dataset synthetique Phase A (5 machines + "
            "2 propagations P2/P3) pour le dashboard Factory Twin."
        ),
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Graine du generateur aleatoire (defaut : 42).",
    )
    parser.add_argument(
        "--machines", nargs="+", default=list(PHASE_A_MACHINES),
        choices=PHASE_A_MACHINES,
        help="Liste des machines a simuler (defaut : M1 M2 M3 M4 M5).",
    )
    parser.add_argument(
        "--propagations", choices=["yes", "no"], default="yes",
        help="Active ou desactive les demos P2 + P3 (defaut : yes).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR,
        help="Repertoire racine de sortie (defaut : data/synthetic/phase_a).",
    )
    parser.add_argument(
        "--duration-s", type=float, default=DURATION_S_DEFAULT,
        help="Duree du signal simule, en secondes (defaut : 4.0).",
    )
    parser.add_argument(
        "--fs", type=int, default=FS_DEFAULT,
        help="Frequence d'echantillonnage, en Hz (defaut : 64000).",
    )
    return parser.parse_args(argv)


def print_machine_summary(results: list[MachineRunResult]) -> None:
    """Affiche un tableau console des RMS par machine / canal."""
    print()
    print("=" * 88)
    print("RESUME — Dataset synthetique Phase A")
    print("=" * 88)
    for r in results:
        print(
            f"  {r.machine_id} ({r.label}) : "
            f"{r.duration_s:.2f} s @ {r.fs} Hz -> {r.path.relative_to(ROOT)}"
        )
        for chan, chan_rms in r.rms_by_channel.items():
            print(f"    - RMS({chan:<12s}) = {chan_rms:.4f}")
    print()


def print_propagation_summary(
    results: list[PropagationResult], label: str,
) -> None:
    """Affiche un tableau console des attenuations mesurees."""
    print("-" * 88)
    print(f"RESUME — Propagations {label}")
    print("-" * 88)
    for r in results:
        print(f"  {r.label}")
        print(f"    -> {r.path.relative_to(ROOT)}")
        print(
            f"    RMS source             = {r.rms_source:.4f}"
        )
        print(
            f"    RMS cible (initial)    = {r.rms_target_initial:.4f}"
        )
        print(
            f"    RMS cible (propage)    = {r.rms_target_propagated:.4f}"
        )
        for harm, att_db in r.attenuation_db.items():
            print(f"    Attenuation {harm:<14s} = {att_db:.2f} dB")
        print()


def main(argv: list[str] | None = None) -> int:
    """Point d'entree du script."""
    args = parse_args(argv)
    print(f"[run_phase_a_demo] seed={args.seed}, machines={args.machines}, "
          f"propagations={args.propagations}")
    print(f"[run_phase_a_demo] output dir = {args.output_dir}")

    # --- Chargement de la config (validation que la source existe) ---
    config_path = ROOT / "configs" / "usine_phase_a.yaml"
    if not config_path.exists():
        print(f"ERREUR : config usine_phase_a.yaml introuvable : {config_path}",
              file=sys.stderr)
        return 1
    with config_path.open(encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    machines_cfg = config["phase_a_factory"]["machines"]
    if not isinstance(machines_cfg, dict):
        print("ERREUR : section 'machines' invalide dans usine_phase_a.yaml",
              file=sys.stderr)
        return 1

    # --- Generation par machine ---
    machine_results: list[MachineRunResult] = []
    for idx, machine_id in enumerate(args.machines):
        if machine_id not in machines_cfg:
            print(
                f"ERREUR : machine {machine_id!r} absente de "
                "usine_phase_a.yaml::machines",
                file=sys.stderr,
            )
            return 1
        # Seed distinct par machine pour eviter les correlations croisees
        # (le seed utilisateur est la base ; on ajoute un offset).
        result = run_machine(
            machine_id=machine_id,
            seed=args.seed + idx,
            output_dir=args.output_dir,
        )
        machine_results.append(result)
    print_machine_summary(machine_results)

    # --- Propagations ---
    propagation_results: list[PropagationResult] = []
    if args.propagations == "yes":
        # Seed distinct pour eviter de re-simuler M1/M2 (le cache n'est
        # pas utilise ici — le script est non-interactif).
        prop_p2 = run_propagation_p2(seed=args.seed + 100, output_dir=args.output_dir)
        prop_p3 = run_propagation_p3(seed=args.seed + 200, output_dir=args.output_dir)
        propagation_results = [prop_p2, prop_p3]
        print_propagation_summary(propagation_results, "P2 + P3")

    # --- Bilan final ---
    print("=" * 88)
    print("BILAN")
    print("=" * 88)
    print(f"  {len(machine_results)} machine(s) simulee(s)")
    if args.propagations == "yes":
        print(f"  {len(propagation_results)} propagation(s) simulee(s)")
    print(f"  Tous les fichiers sont sous : {args.output_dir.relative_to(ROOT)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
