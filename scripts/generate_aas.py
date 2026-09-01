#!/usr/bin/env python3
"""Génère 5 fichiers YAML AAS (un par machine Phase A) depuis
`configs/usine_phase_a.yaml` vers `reports/aas/`.

**Cible :** Phase A Factory Twin (CDC §3.1), 5 machines :
moteur, pompe, réducteur, convoyeur, presse.

**Métamodèle :** Asset Administration Shell (IEC 63278-1). Pour
chaque machine on produit 2 submodèles :
  - `Nameplate` : caractéristiques constructeur (id, label, type,
    puissance, vitesse, roulements)
  - `ConditionMonitoring` : capteurs prioritaires (références vers
    `configs/sensor_catalog.yaml`) + défauts ciblés (mode, signature,
    ISO 15243)

**Discipline "0 mock" :** la sortie est une **représentation
structurée** du fichier YAML d'entrée, sans aucune invention de
valeur. Les champs `confidence` et `source_citation` du fichier
source sont propagés tels quels.

Usage :
    uv run python scripts/generate_aas.py
    uv run python scripts/generate_aas.py --config configs/usine_phase_a.yaml --outdir reports/aas
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Permet l'import du package `src.*` quel que soit le cwd.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.simulation.aas import (  # noqa: E402  (import apres sys.path)
    AssetAdministrationShell,
    Property,
    Submodel,
)

PHASE_A_MACHINES = ("M1", "M2", "M3", "M4", "M5")


# ---------------------------------------------------------------------------
# Construction des submodèles
# ---------------------------------------------------------------------------

def _make_property(
    id_short: str,
    value: object,
    value_type: str,
    semantic_id: str = "",
    confidence: str = "confirmed",
    source_citation: str = "",
) -> Property:
    """Construit une `Property` AAS en propageant `confidence`/`source_citation`.

    Helper local -- toutes les `Property` du générateur passent par
    ici pour garantir la cohérence des métadonnées "0 mock".
    """
    return Property(
        id_short=id_short,
        value_type=value_type,  # type: ignore[arg-type]
        value=value,
        semantic_id=semantic_id,
        confidence=confidence,
        source_citation=source_citation,
    )


def _build_nameplate(machine_id: str, mcfg: dict) -> Submodel:
    """Construit le submodèle `Nameplate` pour une machine.

    Champs documentés (selon `machine_id`) : label, type ISO 20816-3,
    sous-type, puissance, vitesse nominale, plage VFD, roulements.
    Les champs absents du YAML ne sont pas ajoutés (pas de mock).
    """
    props: list[Property] = [
        _make_property(
            id_short="MachineID",
            value=machine_id,
            value_type="xs:string",
            semantic_id="https://admin-shell.io/sandbox/Nameplate/MachineID",
            confidence="confirmed",
            source_citation="configs/usine_phase_a.yaml::machines.M1.MachineID",
        ),
        _make_property(
            id_short="Label",
            value=str(mcfg.get("label", "")),
            value_type="xs:string",
            semantic_id="https://admin-shell.io/sandbox/Nameplate/Label",
            confidence=str(mcfg.get("confidence_global", "confirmed")),
            source_citation=str(mcfg.get("label_citation", "")) or "configs/usine_phase_a.yaml::machines.<id>.label",
        ),
        _make_property(
            id_short="MachineType",
            value=str(mcfg.get("type", "")),
            value_type="xs:string",
            semantic_id="https://admin-shell.io/sandbox/Nameplate/MachineType",
            confidence="confirmed",
            source_citation="configs/application_types.yaml (taxonomie ISO 20816-3) -- etendu pour belt_conveyor et mechanical_press (hors ISO)",
        ),
    ]

    subtype = mcfg.get("subtype")
    if subtype is not None:
        props.append(_make_property(
            id_short="SubType",
            value=str(subtype),
            value_type="xs:string",
            confidence=str(mcfg.get("subtype_confidence", "inferred")),
            source_citation="configs/usine_phase_a.yaml::machines.<id>.subtype",
        ))

    power_kw = mcfg.get("power_kw")
    if power_kw is not None:
        props.append(_make_property(
            id_short="PowerKW",
            value=float(power_kw),
            value_type="xs:float",
            semantic_id="https://admin-shell.io/sandbox/Nameplate/Power",
            confidence=str(mcfg.get("power_confidence", "inferred")),
            source_citation=str(mcfg.get("power_citation", "")),
        ))

    # Vitesse nominale : deux champs possibles dans le YAML
    #   - `nominal_speed_rpm` (M1, M2, M4)
    #   - `nominal_speed_rpm_input` + `nominal_speed_rpm_output` (M3 reducteur)
    nom_rpm = mcfg.get("nominal_speed_rpm")
    nom_rpm_in = mcfg.get("nominal_speed_rpm_input")
    nom_rpm_out = mcfg.get("nominal_speed_rpm_output")
    if nom_rpm is not None:
        props.append(_make_property(
            id_short="NominalSpeedRPM",
            value=float(nom_rpm),
            value_type="xs:float",
            semantic_id="https://admin-shell.io/sandbox/Nameplate/NominalSpeed",
            confidence=str(mcfg.get("nominal_speed_confidence", "inferred")),
            source_citation=str(mcfg.get("nominal_speed_citation", "")),
        ))
    if nom_rpm_in is not None:
        props.append(_make_property(
            id_short="NominalSpeedRPMInput",
            value=float(nom_rpm_in),
            value_type="xs:float",
            confidence=str(mcfg.get("nominal_speed_confidence", "inferred")),
            source_citation=str(mcfg.get("nominal_speed_citation", "")),
        ))
    if nom_rpm_out is not None:
        props.append(_make_property(
            id_short="NominalSpeedRPMOutput",
            value=float(nom_rpm_out),
            value_type="xs:float",
            confidence=str(mcfg.get("nominal_speed_confidence", "inferred")),
            source_citation=str(mcfg.get("nominal_speed_citation", "")),
        ))

    vfd = mcfg.get("vfd_range_rpm")
    if vfd is not None and isinstance(vfd, dict):
        props.append(_make_property(
            id_short="VFDRangeMinRPM",
            value=float(vfd.get("min", 0)),
            value_type="xs:float",
            confidence=str(mcfg.get("vfd_range_confidence", "inferred")),
            source_citation=str(mcfg.get("vfd_range_citation", "")),
        ))
        props.append(_make_property(
            id_short="VFDRangeMaxRPM",
            value=float(vfd.get("max", 0)),
            value_type="xs:float",
            confidence=str(mcfg.get("vfd_range_confidence", "inferred")),
            source_citation=str(mcfg.get("vfd_range_citation", "")),
        ))

    cycle_freq_hz = mcfg.get("cycle_freq_hz")
    if cycle_freq_hz is not None:
        props.append(_make_property(
            id_short="CycleFrequencyHz",
            value=float(cycle_freq_hz),
            value_type="xs:float",
            confidence=str(mcfg.get("cycle_freq_confidence", "inferred")),
            source_citation=str(mcfg.get("cycle_freq_citation", "")),
        ))

    bearings = mcfg.get("bearings")
    if bearings is not None and isinstance(bearings, dict):
        # Un `Property` par roulement (un seul coupleur par cle),
        # prefixe par `Bearing_` pour eviter collision d'id_short.
        for pos, ref in bearings.items():
            if ref is None:
                continue
            # Sanitize key (id_short doit etre CamelCase ou snake_case sans espace)
            pos_safe = pos.replace(" ", "_")
            props.append(_make_property(
                id_short=f"Bearing_{pos_safe}",
                value=str(ref),
                value_type="xs:string",
                confidence=str(mcfg.get("bearings_confidence", "inferred")),
                source_citation=str(mcfg.get("bearings_citation", "")),
            ))

    return Submodel(
        id=f"urn:aas:phaseA:{machine_id}:submodel:Nameplate",
        id_short="Nameplate",
        semantic_id="https://admin-shell.io/idta/SubmodelTemplates/Nameplate/3/0",
        properties=props,
    )


def _build_condition_monitoring(machine_id: str, mcfg: dict) -> Submodel:
    """Construit le submodèle `ConditionMonitoring` pour une machine.

    Champs documentés :
      - `PrioritySensors` : liste de références (ids) vers
        `configs/sensor_catalog.yaml` (stocké comme Property string
        jointe par virgule -- un AAS Property ne peut pas etre une
        liste de strings ; les futures versions AAS supporteront
        `SubmodelElementCollection` mais Phase A s'en tient aux
        `Property`).
      - `TargetedFaults` : idem, JSON inline (mode, signature, ISO 15243)
        en string pour rester strictement dans le périmètre Phase A.
    """
    sensors = mcfg.get("priority_sensors", []) or []
    sensor_strs = []
    for s in sensors:
        if isinstance(s, dict):
            sid = s.get("id", "")
            loc = s.get("location", "")
            rat = s.get("rationale", "")
            sensor_strs.append(f"{sid}@{loc} ({rat})")
        else:
            sensor_strs.append(str(s))
    sensors_value = " | ".join(sensor_strs)

    faults = mcfg.get("targeted_faults", []) or []
    fault_strs = []
    for f in faults:
        if isinstance(f, dict):
            mode = f.get("mode", "")
            sig = f.get("signature", "")
            iso = f.get("iso_15243_ref", "")
            prop = f.get("propagation", "")
            fault_strs.append(f"{mode} [iso={iso}, prop={prop}] sig='{sig}'")
        else:
            fault_strs.append(str(f))
    faults_value = " | ".join(fault_strs)

    props: list[Property] = [
        _make_property(
            id_short="PrioritySensors",
            value=sensors_value,
            value_type="xs:string",
            confidence="inferred",
            source_citation="configs/usine_phase_a.yaml::machines.<id>.priority_sensors",
        ),
        _make_property(
            id_short="TargetedFaults",
            value=faults_value,
            value_type="xs:string",
            confidence="inferred",
            source_citation=str(mcfg.get("targeted_faults_citation", "")) or "configs/usine_phase_a.yaml::machines.<id>.targeted_faults",
        ),
        _make_property(
            id_short="GlobalConfidence",
            value=str(mcfg.get("confidence_global", "uncalibrated")),
            value_type="xs:string",
            confidence="confirmed",
            source_citation="configs/usine_phase_a.yaml::machines.<id>.confidence_global",
        ),
    ]

    return Submodel(
        id=f"urn:aas:phaseA:{machine_id}:submodel:ConditionMonitoring",
        id_short="ConditionMonitoring",
        semantic_id="https://admin-shell.io/idta/SubmodelTemplates/ConditionMonitoring/1/0",
        properties=props,
    )


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def aas_to_dict(aas: AssetAdministrationShell) -> dict:
    """Convertit un `AssetAdministrationShell` en `dict` compatible YAML.

    Le format suit la convention "AAS-as-YAML" simplifiée (non
    normalisée IEC — Phase A s'en tient à un sous-ensemble lisible).
    Les cles `id`, `id_short`, `asset_kind`, `submodels` sont stables
    et permettent une consommation future par un client AAS conforme.
    """
    return {
        "id": aas.id,
        "id_short": aas.id_short,
        "asset_kind": aas.asset_kind,
        "submodels": [
            {
                "id": sm.id,
                "id_short": sm.id_short,
                "semantic_id": sm.semantic_id,
                "properties": [
                    {
                        "id_short": p.id_short,
                        "value_type": p.value_type,
                        "value": p.value,
                        "semantic_id": p.semantic_id,
                        "confidence": p.confidence,
                        "source_citation": p.source_citation,
                    }
                    for p in sm.properties
                ],
            }
            for sm in aas.submodels
        ],
    }


def aas_from_dict(data: dict) -> AssetAdministrationShell:
    """Reconstruit un `AssetAdministrationShell` depuis un `dict` YAML.

    Utilisé par les tests pour valider la sérialisation aller-retour.
    Les champs inconnus sont ignorés silencieusement (forward-
    compatibility).
    """
    aas = AssetAdministrationShell(
        id=str(data["id"]),
        id_short=str(data["id_short"]),
        asset_kind=data.get("asset_kind", "Instance"),  # type: ignore[arg-type]
    )
    for sm_data in data.get("submodels", []) or []:
        sm = Submodel(
            id=str(sm_data["id"]),
            id_short=str(sm_data["id_short"]),
            semantic_id=str(sm_data.get("semantic_id", "")),
        )
        for p_data in sm_data.get("properties", []) or []:
            sm.add_property(Property(
                id_short=str(p_data["id_short"]),
                value_type=str(p_data["value_type"]),  # type: ignore[arg-type]
                value=p_data["value"],
                semantic_id=str(p_data.get("semantic_id", "")),
                confidence=str(p_data.get("confidence", "confirmed")),
                source_citation=str(p_data.get("source_citation", "")),
            ))
        aas.add_submodel(sm)
    return aas


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build_aas(machine_id: str, mcfg: dict) -> AssetAdministrationShell:
    """Construit un AAS complet (2 submodèles) pour une machine."""
    aas = AssetAdministrationShell(
        id=f"urn:aas:phaseA:{machine_id}",
        id_short=f"{machine_id}_{str(mcfg.get('label', machine_id)).replace(' ', '_')}",
    )
    aas.add_submodel(_build_nameplate(machine_id, mcfg))
    aas.add_submodel(_build_condition_monitoring(machine_id, mcfg))
    return aas


def generate(
    config_path: Path,
    outdir: Path,
) -> list[Path]:
    """Génère les 5 fichiers AAS YAML dans `outdir`.

    Retourne la liste des chemins écrits (utilisée par le main() pour
    le log et par les tests pour vérifier que la sortie est stable).
    """
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "phase_a_factory" not in raw:
        raise ValueError(
            f"Config {config_path!s} : cle racine 'phase_a_factory' absente"
        )
    machines_raw = raw["phase_a_factory"].get("machines", {})

    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for mid in PHASE_A_MACHINES:
        if mid not in machines_raw:
            # Machine non listée dans le YAML : on documente son absence
            # mais on n'invente rien (regle "0 mock").
            print(f"  [WARN] {mid} absent de {config_path.name} -- skip", file=sys.stderr)
            continue
        aas = build_aas(mid, machines_raw[mid])
        out_path = outdir / f"aas_{mid}.yaml"
        out_path.write_text(
            yaml.safe_dump(aas_to_dict(aas), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        written.append(out_path)
        # Affichage : chemin relatif a ROOT si possible, sinon absolu.
        try:
            display = out_path.relative_to(ROOT)
        except ValueError:
            display = out_path
        print(f"  [OK]   {mid} -> {display}")
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genere les fichiers AAS (IEC 63278-1) pour la Phase A Factory Twin"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "usine_phase_a.yaml",
        help="Chemin du fichier YAML source (defaut : configs/usine_phase_a.yaml)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "reports" / "aas",
        help="Repertoire de sortie (defaut : reports/aas/)",
    )
    args = parser.parse_args()

    if not args.config.exists():
        print(f"[ERROR] Config introuvable : {args.config.resolve()}", file=sys.stderr)
        return 1

    print(f"Generation AAS Phase A : {len(PHASE_A_MACHINES)} machines")
    written = generate(args.config, args.outdir)
    print(f"OK : {len(written)} fichiers ecrits dans {args.outdir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
