"""Dataclasses Asset Administration Shell (AAS) — IEC 63278-1 (Part 1).

Implémentation strictement minimale des éléments du métamodèle AAS
nécessaires à la sérialisation YAML des 5 machines de la Phase A du
Factory Twin. Cette implémentation n'est PAS un SDK complet : elle
sélectionne uniquement les champs utiles à la simulation Factory Twin
et au commissioning terrain.

**Sourcé :**
- IEC 63278-1:2024 "Asset Administration Shell — Part 1: Metamodel"
  (successeur de la spécification Plattform Industrie 4.0
  "Details of the Asset Administration Shell").
- IDTA submodel templates (Industrial Digital Twin Association) :
  `Nameplate` (v3.0) et `ConditionMonitoring` (v1.0).

**Discipline "0 mock" :** les valeurs des `Property.value` ne sont
jamais inventées dans ce module — elles proviennent toujours de
`configs/usine_phase_a.yaml` ou d'un autre fichier de configuration
sourcé. Le module n'est qu'une structure de transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Énumérations du métamodèle (sous-ensemble strictement nécessaire Phase A)
# ---------------------------------------------------------------------------

# `AssetKind` selon IEC 63278-1 §6.2.3. Limitée à "Instance" pour la Phase A :
# chaque AAS représente une machine réelle (asset physique) — pas un "Type"
# (asset générique de catalogue).
AssetKind = Literal["Instance", "Type"]

# Types de valeur acceptés pour une `Property`. Sous-ensemble des XSD primitives
# utilisées dans les submodel templates AAS (IDTA) :
# - `xs:string`, `xs:int`, `xs:float`, `xs:boolean`, `xs:dateTime` (ISO 8601)
ValueType = Literal["xs:string", "xs:int", "xs:float", "xs:boolean", "xs:dateTime"]


# ---------------------------------------------------------------------------
# Éléments du métamodèle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Property:
    """Élément terminal d'un submodèle AAS (IEC 63278-1 §6.4).

    Représente un couple (clé, valeur typée) annoté optionnellement par
    un identifiant sémantique (IRI selon la pratique IDTA).

    Attributs :
        id_short : identifiant court (séquence de lettres/chiffres/`_`/`-`).
            Doit être unique au sein du submodèle parent.
        value_type : type XSD de la valeur (`xs:float`, `xs:string`, ...).
        value : valeur stockée. Le type Python doit correspondre à
            `value_type` (cette correspondance est validée par
            `validate_property_types`).
        semantic_id : IRI optionnel référençant un concept d'un dictionnaire
            (ex. ECLASS, IEC CDD). Chaîne vide si non spécifié.
        confidence : niveau de confiance de la valeur — `confirmed`,
            `inferred`, `estimated` ou `uncalibrated`. Voir règle
            "0 mock" du projet (`docs/audit_zero_mock_2026-09-01.md`).
            `uncalibrated` = champ structurel nécessaire mais pas
            encore calibré (squelette SA1 : cycle_time_s, mtbf_h, etc.).
        source_citation : description textuelle de la source primaire de
            la valeur (catalogue, fiche technique, mesure). Chaîne vide si
            non documenté.
    """

    id_short: str
    value_type: ValueType
    value: Any
    semantic_id: str = ""
    confidence: str = "confirmed"
    source_citation: str = ""

    def __post_init__(self) -> None:
        # Validation des invariants structurels (pas de mock silencieux) :
        # un `id_short` vide ou avec espaces casserait la sérialisation AAS.
        if not self.id_short or not self.id_short.strip():
            raise ValueError(
                f"Property.id_short vide ou blanc : {self.id_short!r}"
            )
        if " " in self.id_short:
            raise ValueError(
                f"Property.id_short contient des espaces : {self.id_short!r}"
                " (IEC 63278-1 : CamelCase/snake_case uniquement, pas d'espace)"
            )
        if self.confidence not in {"confirmed", "inferred", "estimated", "uncalibrated"}:
            raise ValueError(
                f"Property.confidence invalide : {self.confidence!r}"
                " (valeurs acceptees : confirmed, inferred, estimated, uncalibrated)"
            )
        if self.value_type == "xs:int" and not isinstance(self.value, int):
            raise ValueError(
                f"Property {self.id_short!r} : value_type=xs:int mais "
                f"value={self.value!r} (type {type(self.value).__name__})"
            )
        if self.value_type == "xs:float" and not isinstance(self.value, (int, float)):
            raise ValueError(
                f"Property {self.id_short!r} : value_type=xs:float mais "
                f"value={self.value!r} (type {type(self.value).__name__})"
            )
        if self.value_type == "xs:boolean" and not isinstance(self.value, bool):
            raise ValueError(
                f"Property {self.id_short!r} : value_type=xs:boolean mais "
                f"value={self.value!r} (type {type(self.value).__name__})"
            )
        if self.value_type == "xs:string" and not isinstance(self.value, str):
            raise ValueError(
                f"Property {self.id_short!r} : value_type=xs:string mais "
                f"value={self.value!r} (type {type(self.value).__name__})"
            )


@dataclass
class Submodel:
    """Submodèle AAS (IEC 63278-1 §6.3).

    Regroupement sémantique de propriétés. En Phase A, deux submodèles
    par machine : `Nameplate` (caractéristiques constructeur) et
    `ConditionMonitoring` (capteurs et grandeurs surveillées).

    Attributs :
        id : identifiant global (souvent URN ou IRI).
        id_short : identifiant court lisible (ex. `Nameplate`,
            `ConditionMonitoring`).
        semantic_id : IRI pointant vers la définition du submodèle
            (IDTA template ou dictionnaire).
        properties : liste des `Property` appartenant au submodèle.
    """

    id: str
    id_short: str
    semantic_id: str = ""
    properties: list[Property] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError(
                f"Submodel.id vide ou blanc : {self.id!r}"
            )
        if not self.id_short or not self.id_short.strip():
            raise ValueError(
                f"Submodel.id_short vide ou blanc : {self.id_short!r}"
            )
        # Unicit\u00e9 des id_short au sein du submod\u00e8le (sinon : collision
        # \u00e0 la s\u00e9rialisation YAML et perte d'information).
        seen: set[str] = set()
        for prop in self.properties:
            if prop.id_short in seen:
                raise ValueError(
                    f"Submodel {self.id_short!r} : doublon d'id_short "
                    f"sur la Property {prop.id_short!r}"
                )
            seen.add(prop.id_short)

    def add_property(self, prop: Property) -> None:
        """Ajoute une propriété en vérifiant l'unicité d'`id_short`."""
        if any(p.id_short == prop.id_short for p in self.properties):
            raise ValueError(
                f"Submodel {self.id_short!r} : id_short {prop.id_short!r} "
                "deja present"
            )
        self.properties.append(prop)


@dataclass
class AssetAdministrationShell:
    """Asset Administration Shell — IEC 63278-1 §6.1.

    Enveloppe numérique d'un asset physique (ici : une machine de
    l'usine). En Phase A : un AAS = une machine (pas de hiérarchie
    multi-AAS — un AAS d'atelier sera ajouté en Phase B si besoin).

    Attributs :
        id : identifiant global (URI/URN) de l'AAS, unique sur le
            réseau. Convention Phase A : `urn:aas:phaseA:<machine_id>`.
        id_short : identifiant court lisible, ex. `M1_Motor`.
        asset_kind : `Instance` (asset physique identifié) ou `Type`
            (template d'asset). Phase A = `Instance` uniquement.
        submodels : liste des submodèles rattachés à cet asset.
    """

    id: str
    id_short: str
    asset_kind: AssetKind = "Instance"
    submodels: list[Submodel] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError(
                f"AAS.id vide ou blanc : {self.id!r}"
            )
        if not self.id_short or not self.id_short.strip():
            raise ValueError(
                f"AAS.id_short vide ou blanc : {self.id_short!r}"
            )
        if self.asset_kind not in ("Instance", "Type"):
            raise ValueError(
                f"AAS.asset_kind invalide : {self.asset_kind!r}"
                " (IEC 63278-1 : 'Instance' ou 'Type')"
            )
        # Unicit\u00e9 des id_short de submod\u00e8les au sein de l'AAS.
        seen: set[str] = set()
        for sm in self.submodels:
            if sm.id_short in seen:
                raise ValueError(
                    f"AAS {self.id_short!r} : doublon d'id_short sur le "
                    f"Submodel {sm.id_short!r}"
                )
            seen.add(sm.id_short)

    def add_submodel(self, submodel: Submodel) -> None:
        """Ajoute un submodèle en vérifiant l'unicité d'`id_short`."""
        if any(s.id_short == submodel.id_short for s in self.submodels):
            raise ValueError(
                f"AAS {self.id_short!r} : id_short {submodel.id_short!r} "
                "deja present"
            )
        self.submodels.append(submodel)

    def get_submodel(self, id_short: str) -> Submodel | None:
        """Récupère un submodèle par son `id_short`, ou `None`."""
        for sm in self.submodels:
            if sm.id_short == id_short:
                return sm
        return None


# ---------------------------------------------------------------------------
# Validation de coh\u00e9rence multi-niveaux
# ---------------------------------------------------------------------------

def validate_aas(aas: AssetAdministrationShell) -> list[str]:
    """Vérifie la cohérence interne d'un AAS.

    Retourne une liste de messages d'avertissement (vide si tout est OK).
    Les erreurs structurelles (id vide, doublons, types incohérents)
    sont levées par les `__post_init__` ; cette fonction lève des
    avertissements sur des questions de fond (sémantique, complétude).

    Vérifications :
        - `asset_kind=Instance` est attendu en Phase A.
        - Les submodèles `Nameplate` et `ConditionMonitoring` sont
          recommandés (pas obligatoires, mais leur absence est notée).
    """
    warnings: list[str] = []
    if aas.asset_kind != "Instance":
        warnings.append(
            f"AAS {aas.id_short!r} : asset_kind={aas.asset_kind!r} "
            "inattendu en Phase A (uniquement 'Instance')"
        )
    submodel_ids = {sm.id_short for sm in aas.submodels}
    if "Nameplate" not in submodel_ids:
        warnings.append(
            f"AAS {aas.id_short!r} : submodel 'Nameplate' absent "
            "(recommande pour identification machine)"
        )
    if "ConditionMonitoring" not in submodel_ids:
        warnings.append(
            f"AAS {aas.id_short!r} : submodel 'ConditionMonitoring' absent "
            "(recommande pour capteurs et seuils)"
        )
    return warnings


__all__ = [
    "AssetAdministrationShell",
    "AssetKind",
    "Property",
    "Submodel",
    "ValueType",
    "validate_aas",
]
