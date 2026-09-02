"""Frequences caracteristiques de trains d'engrenages (reducteurs/multiplicateurs),
generalise a N etages et a plusieurs types de denture. Voir docs/theorie_reference.md
§2bis (taxonomie roulements/paliers) et §2 (fondement physique BPFO/BPFI/BSF/FTF,
meme logique appliquee ici aux engrenages).

Loi physique commune (confirmed) a tous les types d'engrenages a AXES FIXES -
droits (spur), helicoidaux, coniques droits, spiro-coniques, roue-et-vis :
la frequence d'engrenement (GMF, Gear Mesh Frequency) est invariante le long
de l'engrenement :

    GMF = N_menant * f_menant = N_mene * f_mene

ou N est le nombre de dents (pour une roue-et-vis, N_menant = nombre de
filets/"starts" de la vis, PAS un nombre de dents au sens ordinaire - meme
formule, interpretation differente). Cette identite sert de test unitaire,
meme principe que BPFO+BPFI = n*fr dans fault_frequencies.py.

Le train EPICYCLOIDAL (planetaire) suit une loi differente (vitesse relative
au porte-satellites, pas une simple cascade pignon/couronne) - volontairement
NON implemente ici plutot que d'appliquer a tort la formule des engrenages a
axes fixes, voir PlanetaryNotImplementedError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.features.fault_frequencies import all_fault_frequencies

ReductionType = Literal["spur", "helical", "straight_bevel", "spiral_bevel", "worm"]

_SUPPORTED_TYPES: frozenset[str] = frozenset(
    {"spur", "helical", "straight_bevel", "spiral_bevel", "worm"}
)


class PlanetaryNotImplementedError(NotImplementedError):
    """Le train epicycloidal (planetaire) n'est pas modelise ici.

    Sa cinematique n'est pas une simple cascade menant/mene : la frequence
    d'engrenement depend de la vitesse RELATIVE au porte-satellites, pas de
    la vitesse absolue de l'arbre d'entree. Pour un train a couronne fixe
    (cas le plus courant), la formule de reference est :

        f_porte_satellites = f_soleil * Z_soleil / (Z_soleil + Z_couronne)
        GMF = Z_soleil * (f_soleil - f_porte_satellites)
            = Z_couronne * f_porte_satellites

    Non implemente plutot que devine - a ajouter si un reducteur planetaire
    reel doit etre modelise, avec verification manuelle des deux formules
    ci-dessus (elles doivent donner le meme GMF, meme principe de test que
    le reste de ce module)."""


@dataclass(frozen=True)
class GearStage:
    """Un etage de reduction/multiplication.

    Pour 'worm' (roue et vis) : `driving_teeth` = nombre de filets de la vis
    (1, 2 ou 4 filets typiquement, PAS un nombre de dents ordinaire),
    `driven_teeth` = nombre de dents de la roue creuse. La loi GMF reste
    identique (voir docstring module) - c'est ce qui permet de traiter tous
    les types de denture avec le meme calcul en cascade.
    """

    reduction_type: ReductionType
    driving_teeth: int  # menant : pignon, ou nombre de filets pour une vis
    driven_teeth: int  # mene : roue/couronne

    def __post_init__(self) -> None:
        if self.reduction_type not in _SUPPORTED_TYPES:
            raise ValueError(
                f"reduction_type={self.reduction_type!r} non supporte. "
                f"Types geres : {sorted(_SUPPORTED_TYPES)}. Le planetaire "
                f"(epicycloidal) suit une loi differente, voir "
                f"PlanetaryNotImplementedError."
            )
        if self.driving_teeth <= 0 or self.driven_teeth <= 0:
            raise ValueError("driving_teeth et driven_teeth doivent etre strictement positifs.")

    @property
    def ratio(self) -> float:
        """Rapport de reduction de cet etage (>1 = demultiplication, <1 = multiplication)."""
        return self.driven_teeth / self.driving_teeth


@dataclass(frozen=True)
class StageFrequencies:
    """Resultat du calcul pour un etage - toutes les frequences en Hz."""

    stage_index: int
    reduction_type: str
    ratio: float
    f_in_hz: float
    f_out_hz: float
    gmf_hz: float
    gmf_harmonics_hz: dict[int, float]  # {2: 2xGMF, 3: 3xGMF, ...}


def compute_gear_train(
    input_rpm: float,
    stages: list[GearStage],
    n_harmonics: int = 3,
) -> list[StageFrequencies]:
    """Calcule automatiquement, en cascade, les frequences de chaque etage
    d'un train d'engrenages a N etages a partir de la seule vitesse d'entree.

    "Automatique" au sens ou chaque etage prend en entree la frequence de
    SORTIE de l'etage precedent - pas besoin de re-deriver les frequences
    intermediaires a la main pour un train mixte (ex. roue-et-vis en premier
    etage suivi d'un etage spiro-conique), contrairement a
    src/gearbox/helical.py qui code en dur 2 etages helicoidaux pour la
    simulation Factory Twin. Ce module est la version generale/reutilisable,
    applicable a un reducteur reel quel que soit le nombre d'etages ou le
    melange de types de denture.
    """
    if input_rpm <= 0:
        raise ValueError(f"input_rpm={input_rpm} doit etre strictement positif.")
    if not stages:
        raise ValueError("Au moins un etage requis.")

    results: list[StageFrequencies] = []
    f_in = input_rpm / 60.0
    for i, stage in enumerate(stages, start=1):
        f_out = f_in / stage.ratio
        gmf = stage.driving_teeth * f_in  # == stage.driven_teeth * f_out (invariant, teste)
        harmonics = {h: h * gmf for h in range(2, n_harmonics + 1)}
        results.append(
            StageFrequencies(
                stage_index=i,
                reduction_type=stage.reduction_type,
                ratio=stage.ratio,
                f_in_hz=f_in,
                f_out_hz=f_out,
                gmf_hz=gmf,
                gmf_harmonics_hz=harmonics,
            )
        )
        f_in = f_out  # cascade automatique vers l'etage suivant

    return results


@dataclass(frozen=True)
class GearTrainReport:
    """Rapport de reduction cinematique complet - vue d'ensemble du train en
    plus du detail par etage (StageFrequencies). Le rapport de reduction
    total est le produit des rapports de chaque etage, PAS une simple somme -
    propriete algebrique testee (voir tests/test_gear_frequencies.py)."""

    input_rpm: float
    output_rpm: float
    total_ratio: float
    stages: list[StageFrequencies]

    @property
    def n_stages(self) -> int:
        return len(self.stages)

    @property
    def all_gmf_hz(self) -> dict[int, float]:
        """GMF de chaque etage, indexe par numero d'etage (1-based) - vue
        plate utile pour annoter un spectre (une couleur par etage)."""
        return {s.stage_index: s.gmf_hz for s in self.stages}


def summarize_gear_train(
    input_rpm: float,
    stages: list[GearStage],
    n_harmonics: int = 3,
) -> GearTrainReport:
    """Rapport de reduction cinematique complet : calcule le detail par
    etage (compute_gear_train) PUIS agrege le rapport de reduction total et
    la vitesse de sortie finale - la vue "cahier des charges" d'un
    reducteur (ex. "reducteur 45:1, entree 1450 tr/min -> sortie 32.2 tr/min")
    en plus du detail frequentiel par etage necessaire au diagnostic."""
    stage_results = compute_gear_train(input_rpm, stages, n_harmonics=n_harmonics)
    total_ratio = 1.0
    for stage in stages:
        total_ratio *= stage.ratio
    output_rpm = input_rpm / total_ratio
    return GearTrainReport(
        input_rpm=input_rpm,
        output_rpm=output_rpm,
        total_ratio=total_ratio,
        stages=stage_results,
    )


def first_stage_input_bearing_frequencies(
    input_rpm: float,
    n_balls: int,
    ball_diameter_mm: float,
    pitch_diameter_mm: float,
    contact_angle_deg: float = 0.0,
) -> dict[str, float]:
    """Frequences de defaut du PREMIER train de roulement (portee d'entree du
    reducteur, arbre rapide) - reutilise fault_frequencies.py directement,
    aucune formule dupliquee.

    "Premier" train : le roulement d'entree tourne a la vitesse la plus
    elevee du reducteur (avant toute demultiplication), donc cumule le plus
    de cycles de charge par unite de temps - c'est generalement le premier
    point de surveillance vibratoire sur un moto-reducteur (voir
    docs/theorie_reference.md §2bis, catalogue paliers/roulements)."""
    return all_fault_frequencies(
        n_balls, input_rpm, ball_diameter_mm, pitch_diameter_mm, contact_angle_deg
    )
