"""Registre d'unites et conversions - normalisation multi-sources/multi-capteurs.

Objectif : chaque source (Paderborn, futures sources pression/debit/temperature,
voir docs/scaling_path.md) a ses propres capteurs, dans des unites propres au
constructeur/protocole. Ce module centralise la conversion vers une unite
CANONIQUE par type de grandeur physique, pour que `signal.unit` et
`feature.unit` en base soient toujours dans un referentiel commun, comparable
entre sources - condition necessaire pour toute comparaison cross-source
(objectif explicite du projet, docs/data_model.md).

Ne PAS deviner une unite sans source documentee. Voir CANONICAL_UNITS pour la
liste des grandeurs couvertes et leur unite cible.
"""

from dataclasses import dataclass

CANONICAL_UNITS = {
    "vibration_acceleration": "g",       # acceleration vibratoire
    "vibration_velocity": "mm/s",        # vitesse vibratoire (ISO 20816)
    "current": "A",                      # courant electrique (RMS ou instantane)
    "temperature": "degC",
    "pressure": "bar",
    "flow": "m3/h",
    "rotational_speed": "rpm",
}


@dataclass(frozen=True)
class SensorSpec:
    """Specification d'un capteur : unite native + facteur de conversion vers
    l'unite canonique (value_canonical = value_raw * scale_to_canonical + offset)."""

    quantity: str          # cle de CANONICAL_UNITS
    raw_unit: str          # unite native du capteur/export, ex. "g", "mV", "raw_adc"
    scale_to_canonical: float = 1.0
    offset_to_canonical: float = 0.0
    confidence: str = "confirmed"  # confirmed | inferred | unknown
    source_citation: str = ""


# Registre (source, channel) -> SensorSpec. A completer au fur et a mesure des
# sources ajoutees (voir docs/scaling_path.md et docs/sources_non_paderborn_inventory.md).
SENSOR_REGISTRY: dict[tuple[str, str], SensorSpec] = {
    ("paderborn", "vibration"): SensorSpec(
        quantity="vibration_acceleration",
        raw_unit="g",
        scale_to_canonical=1.0,
        confidence="inferred",
        source_citation=(
            "Capteur : vibration transducer PCB Piezotronics 336C04 (97/F/3, "
            "100 mV/g), charge amplifier Kistler type 5015, filtre 30 kHz 2e ordre "
            "(data/raw/paderborn/K001/measuring_log_K001.pdf). Le fichier .mat ne "
            "documente PAS explicitement si l'export est deja en g ou en volts bruts "
            "(champ Unit vide dans la structure Y) - l'hypothese 'deja en g' est "
            "INFEREE de l'ordre de grandeur des valeurs observees (mediane ~0.07, "
            "max ~4.88 sur K001), physiquement plausible pour un banc de "
            "roulement, mais PAS confirmee par une documentation explicite. "
            "A verifier avant tout calcul ISO 20816 (qui exige mm/s, pas g - "
            "necessite en plus une integration frequentielle acceleration->vitesse, "
            "non implementee ici, voir docs/known_issues.md)."
        ),
    ),
    ("paderborn", "current_1"): SensorSpec(
        quantity="current", raw_unit="A", scale_to_canonical=1.0,
        confidence="inferred",
        source_citation=(
            "Current transformer LEM CKSR 15-NP + Bessel-filter 4e ordre 25kHz "
            "(measuring_log_K001.pdf). Sortie LEM CKSR typiquement deja en A apres "
            "conditionnement, non confirme explicitement dans le .mat (Unit vide)."
        ),
    ),
    ("paderborn", "current_2"): SensorSpec(
        quantity="current", raw_unit="A", scale_to_canonical=1.0,
        confidence="inferred", source_citation="Idem current_1.",
    ),
    ("paderborn", "speed"): SensorSpec(
        quantity="rotational_speed", raw_unit="rpm", scale_to_canonical=1.0,
        confidence="confirmed",
        source_citation=(
            "Mesure directe via arbre de mesure Magtrol TM305 (measuring_log_K001.pdf). "
            "Valeurs observees (~900/~1500 rpm selon condition) correspondent "
            "exactement aux vitesses nominales documentees - confirme, pas infere."
        ),
    ),
}


def get_sensor_spec(source: str, channel: str) -> SensorSpec | None:
    return SENSOR_REGISTRY.get((source, channel))


def to_canonical(value: float, spec: SensorSpec) -> float:
    return value * spec.scale_to_canonical + spec.offset_to_canonical


def canonical_unit_for(quantity: str) -> str:
    if quantity not in CANONICAL_UNITS:
        raise ValueError(f"Grandeur inconnue : {quantity!r}. Ajouter a CANONICAL_UNITS.")
    return CANONICAL_UNITS[quantity]
