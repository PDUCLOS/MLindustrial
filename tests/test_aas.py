"""Tests unitaires sur les dataclasses AAS (IEC 63278-1).

Couvre :
- validation structurelle des `Property` (id_short, value_type, confidence)
- validation structurelle des `Submodel` (id, unicité des id_short)
- validation structurelle des `AssetAdministrationShell` (id, asset_kind, unicité)
- validation de cohérence (submodèles recommandés via `validate_aas`)
- sérialisation/désérialisation YAML aller-retour (round-trip)
- usage réel : construction des 5 AAS Phase A depuis `configs/usine_phase_a.yaml`
  via `scripts/generate_aas.py` puis relecture (chaque AAS doit contenir
  les submodèles `Nameplate` et `ConditionMonitoring` non vides)

**Discipline "0 mock" :** ces tests ne contiennent AUCUN mock
(le brief "0 mock" du projet s'applique au code de production, pas
aux tests, mais on garde la discipline par cohérence — voir
`docs/audit_zero_mock_2026-09-01.md` § 1 qui rappelle que les tests
sont exclus par design, ici on va plus loin en n'utilisant même pas
de fixtures synthétiques inutiles : on lit les vraies configs).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.simulation.aas import (  # noqa: E402  (import apres sys.path)
    AssetAdministrationShell,
    Property,
    Submodel,
    validate_aas,
)
from scripts.generate_aas import (  # noqa: E402
    aas_from_dict,
    aas_to_dict,
    build_aas,
    generate,
)


# ===========================================================================
# 1. Property : invariants structurels
# ===========================================================================

class TestProperty:
    """Tests sur la dataclasse `Property` (élément terminal AAS)."""

    def test_id_short_vide_leve_valueerror(self) -> None:
        with pytest.raises(ValueError, match="id_short vide"):
            Property(
                id_short="",
                value_type="xs:string",
                value="x",
            )

    def test_id_short_avec_espaces_leve_valueerror(self) -> None:
        with pytest.raises(ValueError, match="id_short contient des espaces"):
            Property(
                id_short="Label machine",
                value_type="xs:string",
                value="x",
            )

    def test_confidence_invalide_leve_valueerror(self) -> None:
        with pytest.raises(ValueError, match="confidence invalide"):
            Property(
                id_short="x",
                value_type="xs:string",
                value="x",
                confidence="unspecified",  # non listee
            )

    def test_value_type_int_avec_float_leve_valueerror(self) -> None:
        with pytest.raises(ValueError, match="xs:int"):
            Property(
                id_short="x",
                value_type="xs:int",
                value=1.5,  # float, pas int
            )

    def test_value_type_int_accepte_int(self) -> None:
        p = Property(id_short="x", value_type="xs:int", value=42)
        assert p.value == 42

    def test_value_type_float_accepte_float_et_int(self) -> None:
        p1 = Property(id_short="x", value_type="xs:float", value=1.5)
        p2 = Property(id_short="y", value_type="xs:float", value=3)  # int -> float OK
        assert p1.value == 1.5
        assert p2.value == 3

    def test_value_type_boolean_reprend_int_leve(self) -> None:
        with pytest.raises(ValueError, match="xs:boolean"):
            Property(
                id_short="x",
                value_type="xs:boolean",
                value=1,  # int != bool (meme si True == 1 en Python)
            )

    def test_value_type_string_avec_int_leve(self) -> None:
        with pytest.raises(ValueError, match="xs:string"):
            Property(
                id_short="x",
                value_type="xs:string",
                value=42,
            )

    def test_property_est_immutable(self) -> None:
        """Une `Property` est `frozen=True` : pas de mutation apres construction."""
        p = Property(id_short="x", value_type="xs:string", value="v")
        with pytest.raises(Exception):  # FrozenInstanceError en pratique
            p.value = "nouvelle"  # type: ignore[misc]

    def test_default_confidence_est_confirmed(self) -> None:
        p = Property(id_short="x", value_type="xs:string", value="v")
        assert p.confidence == "confirmed"

    def test_semantic_id_et_source_citation_par_defaut_vides(self) -> None:
        p = Property(id_short="x", value_type="xs:string", value="v")
        assert p.semantic_id == ""
        assert p.source_citation == ""


# ===========================================================================
# 2. Submodel : invariants structurels
# ===========================================================================

class TestSubmodel:
    """Tests sur la dataclasse `Submodel`."""

    def _p(self, id_short: str) -> Property:
        return Property(id_short=id_short, value_type="xs:string", value="v")

    def test_id_vide_leve(self) -> None:
        with pytest.raises(ValueError, match="Submodel.id vide"):
            Submodel(id="", id_short="Nameplate")

    def test_id_short_vide_leve(self) -> None:
        with pytest.raises(ValueError, match="Submodel.id_short vide"):
            Submodel(id="urn:x", id_short="")

    def test_unicite_id_short_property_leve(self) -> None:
        with pytest.raises(ValueError, match="doublon d'id_short"):
            Submodel(
                id="urn:x",
                id_short="Nameplate",
                properties=[self._p("A"), self._p("A")],  # doublon
            )

    def test_add_property_accepte_unique_et_refuse_doublon(self) -> None:
        sm = Submodel(id="urn:x", id_short="Nameplate")
        sm.add_property(self._p("A"))
        sm.add_property(self._p("B"))
        assert len(sm.properties) == 2
        with pytest.raises(ValueError, match="deja present"):
            sm.add_property(self._p("A"))

    def test_properties_par_defaut_vide(self) -> None:
        sm = Submodel(id="urn:x", id_short="Nameplate")
        assert sm.properties == []


# ===========================================================================
# 3. AssetAdministrationShell : invariants structurels
# ===========================================================================

class TestAssetAdministrationShell:
    """Tests sur la dataclasse `AssetAdministrationShell`."""

    def test_id_vide_leve(self) -> None:
        with pytest.raises(ValueError, match="AAS.id vide"):
            AssetAdministrationShell(id="", id_short="M1")

    def test_id_short_vide_leve(self) -> None:
        with pytest.raises(ValueError, match="AAS.id_short vide"):
            AssetAdministrationShell(id="urn:x", id_short="")

    def test_asset_kind_invalide_leve(self) -> None:
        with pytest.raises(ValueError, match="asset_kind invalide"):
            AssetAdministrationShell(id="urn:x", id_short="M1", asset_kind="Both")  # type: ignore[arg-type]

    def test_unicite_id_short_submodels_leve(self) -> None:
        with pytest.raises(ValueError, match="doublon d'id_short sur le Submodel"):
            AssetAdministrationShell(
                id="urn:x",
                id_short="M1",
                submodels=[
                    Submodel(id="urn:x:1", id_short="Nameplate"),
                    Submodel(id="urn:x:2", id_short="Nameplate"),  # doublon
                ],
            )

    def test_add_submodel_accepte_unique_et_refuse_doublon(self) -> None:
        aas = AssetAdministrationShell(id="urn:x", id_short="M1")
        aas.add_submodel(Submodel(id="urn:x:1", id_short="Nameplate"))
        aas.add_submodel(Submodel(id="urn:x:2", id_short="ConditionMonitoring"))
        assert len(aas.submodels) == 2
        with pytest.raises(ValueError, match="deja present"):
            aas.add_submodel(Submodel(id="urn:x:3", id_short="Nameplate"))

    def test_get_submodel(self) -> None:
        aas = AssetAdministrationShell(
            id="urn:x",
            id_short="M1",
            submodels=[Submodel(id="urn:x:1", id_short="Nameplate")],
        )
        assert aas.get_submodel("Nameplate") is not None
        assert aas.get_submodel("Inexistant") is None


# ===========================================================================
# 4. validate_aas : avertissements
# ===========================================================================

class TestValidateAAS:
    """Tests sur la fonction `validate_aas`."""

    def test_aas_complet_pas_d_avertissement(self) -> None:
        aas = AssetAdministrationShell(
            id="urn:x",
            id_short="M1",
            asset_kind="Instance",
            submodels=[
                Submodel(id="urn:x:1", id_short="Nameplate"),
                Submodel(id="urn:x:2", id_short="ConditionMonitoring"),
            ],
        )
        assert validate_aas(aas) == []

    def test_aas_sans_nameplate_avertit(self) -> None:
        aas = AssetAdministrationShell(
            id="urn:x",
            id_short="M1",
            submodels=[Submodel(id="urn:x:1", id_short="ConditionMonitoring")],
        )
        warnings = validate_aas(aas)
        assert any("Nameplate" in w for w in warnings)

    def test_aas_sans_condition_monitoring_avertit(self) -> None:
        aas = AssetAdministrationShell(
            id="urn:x",
            id_short="M1",
            submodels=[Submodel(id="urn:x:1", id_short="Nameplate")],
        )
        warnings = validate_aas(aas)
        assert any("ConditionMonitoring" in w for w in warnings)

    def test_aas_type_asset_kind_non_instance_avertit(self) -> None:
        aas = AssetAdministrationShell(
            id="urn:x",
            id_short="Template",
            asset_kind="Type",
            submodels=[
                Submodel(id="urn:x:1", id_short="Nameplate"),
                Submodel(id="urn:x:2", id_short="ConditionMonitoring"),
            ],
        )
        warnings = validate_aas(aas)
        assert any("asset_kind" in w for w in warnings)


# ===========================================================================
# 5. Sérialisation YAML aller-retour
# ===========================================================================

class TestSerializationRoundTrip:
    """Le couple aas_to_dict / aas_from_dict doit etre involutif."""

    def _aas_test(self) -> AssetAdministrationShell:
        aas = AssetAdministrationShell(
            id="urn:aas:phaseA:M1",
            id_short="M1_Moteur",
        )
        aas.add_submodel(Submodel(
            id="urn:aas:phaseA:M1:submodel:Nameplate",
            id_short="Nameplate",
            semantic_id="https://admin-shell.io/idta/SubmodelTemplates/Nameplate/3/0",
            properties=[
                Property(
                    id_short="MachineID", value_type="xs:string", value="M1",
                    confidence="confirmed",
                    source_citation="configs/usine_phase_a.yaml",
                ),
                Property(
                    id_short="PowerKW", value_type="xs:float", value=75.0,
                    confidence="inferred",
                    source_citation="docs/architecture_usine_simulation.md §3 M1",
                ),
            ],
        ))
        aas.add_submodel(Submodel(
            id="urn:aas:phaseA:M1:submodel:ConditionMonitoring",
            id_short="ConditionMonitoring",
            semantic_id="https://admin-shell.io/idta/SubmodelTemplates/ConditionMonitoring/1/0",
            properties=[
                Property(
                    id_short="PrioritySensors", value_type="xs:string",
                    value="S1_acc_IEPE_100mVg | S2_TC_courant",
                    confidence="inferred",
                    source_citation="configs/usine_phase_a.yaml::priority_sensors",
                ),
            ],
        ))
        return aas

    def test_roundtrip_dict_inverse(self) -> None:
        """aas_to_dict puis aas_from_dict redonne un AAS identique."""
        aas = self._aas_test()
        d = aas_to_dict(aas)
        aas2 = aas_from_dict(d)
        assert aas2.id == aas.id
        assert aas2.id_short == aas.id_short
        assert aas2.asset_kind == aas.asset_kind
        assert len(aas2.submodels) == len(aas.submodels)
        for sm1, sm2 in zip(aas.submodels, aas2.submodels):
            assert sm1.id == sm2.id
            assert sm1.id_short == sm2.id_short
            assert sm1.semantic_id == sm2.semantic_id
            assert len(sm1.properties) == len(sm2.properties)
            for p1, p2 in zip(sm1.properties, sm2.properties):
                assert p1.id_short == p2.id_short
                assert p1.value_type == p2.value_type
                assert p1.value == p2.value
                assert p1.confidence == p2.confidence
                assert p1.semantic_id == p2.semantic_id

    def test_roundtrip_yaml_via_fichier_temporaire(self, tmp_path: Path) -> None:
        """Le YAML sérialisé doit pouvoir etre relu et donner le meme AAS."""
        aas = self._aas_test()
        d = aas_to_dict(aas)
        yaml_path = tmp_path / "aas.yaml"
        yaml_path.write_text(
            yaml.safe_dump(d, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        d_reload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        aas2 = aas_from_dict(d_reload)
        assert aas2.id_short == aas.id_short
        assert len(aas2.submodels) == 2

    def test_aas_to_dict_expose_tous_les_champs(self) -> None:
        aas = self._aas_test()
        d = aas_to_dict(aas)
        assert d["id"] == "urn:aas:phaseA:M1"
        assert d["id_short"] == "M1_Moteur"
        assert d["asset_kind"] == "Instance"
        assert isinstance(d["submodels"], list)
        sm_names = [sm["id_short"] for sm in d["submodels"]]
        assert sm_names == ["Nameplate", "ConditionMonitoring"]


# ===========================================================================
# 6. Generation des 5 AAS Phase A depuis la vraie config projet
# ===========================================================================

class TestPhaseAGeneration:
    """Integration : genere les 5 AAS depuis la config Phase A du projet."""

    @pytest.fixture
    def config_path(self) -> Path:
        return ROOT / "configs" / "usine_phase_a.yaml"

    def test_5_machines_aas_generes(self, tmp_path: Path, config_path: Path) -> None:
        written = generate(config_path, tmp_path)
        assert len(written) == 5
        noms = sorted(p.name for p in written)
        assert noms == ["aas_M1.yaml", "aas_M2.yaml", "aas_M3.yaml",
                        "aas_M4.yaml", "aas_M5.yaml"]

    def test_aas_chacun_a_nameplate_et_condition_monitoring(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """Chaque AAS doit contenir les 2 submodeles recommandes en Phase A."""
        written = generate(config_path, tmp_path)
        for path in written:
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
            aas = aas_from_dict(d)
            sm_names = {sm.id_short for sm in aas.submodels}
            assert "Nameplate" in sm_names, (
                f"{path.name} : pas de submodel Nameplate"
            )
            assert "ConditionMonitoring" in sm_names, (
                f"{path.name} : pas de submodel ConditionMonitoring"
            )
            # validate_aas ne doit pas produire d'avertissement sur les 2 submodeles
            warnings = validate_aas(aas)
            assert warnings == [], f"{path.name} : {warnings}"

    def test_aas_m1_a_les_champs_nameplate_attendus(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """M1 (moteur 75 kW) doit avoir PowerKW=75.0, MachineID='M1', 2 roulements."""
        written = generate(config_path, tmp_path)
        m1_path = next(p for p in written if p.name == "aas_M1.yaml")
        d = yaml.safe_load(m1_path.read_text(encoding="utf-8"))
        aas = aas_from_dict(d)
        nameplate = aas.get_submodel("Nameplate")
        assert nameplate is not None
        props = {p.id_short: p for p in nameplate.properties}
        assert props["MachineID"].value == "M1"
        assert props["PowerKW"].value == 75.0
        assert props["PowerKW"].value_type == "xs:float"
        # Roulements 6309 (DE) et 6308 (NDE)
        assert props["Bearing_drive_end"].value == "6309"
        assert props["Bearing_non_drive_end"].value == "6308"
        # VFD 750-3000 rpm
        assert props["VFDRangeMinRPM"].value == 750
        assert props["VFDRangeMaxRPM"].value == 3000

    def test_aas_m3_reducteur_a_rpm_input_et_output(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """M3 reducteur doit avoir NominalSpeedRPMInput=1500 et Output=250."""
        written = generate(config_path, tmp_path)
        m3_path = next(p for p in written if p.name == "aas_M3.yaml")
        d = yaml.safe_load(m3_path.read_text(encoding="utf-8"))
        aas = aas_from_dict(d)
        nameplate = aas.get_submodel("Nameplate")
        assert nameplate is not None
        props = {p.id_short: p for p in nameplate.properties}
        assert props["NominalSpeedRPMInput"].value == 1500
        assert props["NominalSpeedRPMOutput"].value == 250
        # Le reducteur n'a pas de PowerKW propre (transmissible)
        assert "PowerKW" not in props

    def test_aas_m5_presse_a_cycle_frequency_pas_de_nominal_speed(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """M5 presse : pas de NominalSpeedRPM mais CycleFrequencyHz=1.0."""
        written = generate(config_path, tmp_path)
        m5_path = next(p for p in written if p.name == "aas_M5.yaml")
        d = yaml.safe_load(m5_path.read_text(encoding="utf-8"))
        aas = aas_from_dict(d)
        nameplate = aas.get_submodel("Nameplate")
        assert nameplate is not None
        props = {p.id_short: p for p in nameplate.properties}
        assert "NominalSpeedRPM" not in props
        assert props["CycleFrequencyHz"].value == 1.0

    def test_aas_condition_monitoring_a_targeted_faults_non_vide(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """Chaque submodel ConditionMonitoring doit lister au moins un defaut."""
        written = generate(config_path, tmp_path)
        for path in written:
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
            aas = aas_from_dict(d)
            cm = aas.get_submodel("ConditionMonitoring")
            assert cm is not None
            cm_props = {p.id_short: p for p in cm.properties}
            assert cm_props["TargetedFaults"].value, (
                f"{path.name} : TargetedFaults vide"
            )
            assert cm_props["PrioritySensors"].value, (
                f"{path.name} : PrioritySensors vide"
            )

    def test_generation_cli_script_aboutit(
        self, tmp_path: Path, config_path: Path,
    ) -> None:
        """Le script generate_aas.py doit tourner en CLI et ecrire 5 fichiers."""
        outdir = tmp_path / "aas_out"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_aas.py"),
                "--config", str(config_path),
                "--outdir", str(outdir),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"CLI a echoue (rc={result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        written = sorted(outdir.glob("aas_M*.yaml"))
        assert len(written) == 5
        # Verifier que les fichiers contiennent les 2 submodeles
        for path in written:
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "submodels" in d
            sm_names = {sm["id_short"] for sm in d["submodels"]}
            assert "Nameplate" in sm_names
            assert "ConditionMonitoring" in sm_names


# ===========================================================================
# 7. Sanity check : build_aas (sans passer par generate)
# ===========================================================================

def test_build_aas_renvoie_aas_avec_deux_submodels() -> None:
    mcfg = {
        "label": "Moteur test",
        "type": "electric_motor",
        "subtype": "induction_4poles",
        "power_kw": 75.0,
        "power_confidence": "inferred",
        "power_citation": "docs/architecture_usine_simulation.md §3 M1",
        "nominal_speed_rpm": 1500,
        "nominal_speed_confidence": "confirmed",
        "nominal_speed_citation": "IEC 60034-1",
        "vfd_range_rpm": {"min": 750, "max": 3000},
        "vfd_range_confidence": "inferred",
        "vfd_range_citation": "catalogue ABB ACS580",
        "bearings": {"drive_end": "6309", "non_drive_end": "6308"},
        "bearings_confidence": "inferred",
        "bearings_citation": "docs/architecture_usine_simulation.md §3 M1",
        "priority_sensors": [
            {"id": "S1_acc_IEPE_100mVg", "location": "DE", "rationale": "BPFO"},
        ],
        "targeted_faults": [
            {
                "mode": "broken_rotor_bars",
                "signature": "sidebands fs",
                "iso_15243_ref": "5.4.2",
                "propagation": "P3",
            },
        ],
        "targeted_faults_citation": "theorie_reference.md §4",
        "confidence_global": "uncalibrated",
    }
    aas = build_aas("M1", mcfg)
    assert aas.id == "urn:aas:phaseA:M1"
    sm_names = {sm.id_short for sm in aas.submodels}
    assert sm_names == {"Nameplate", "ConditionMonitoring"}
