"""Detection de valeurs physiquement/mathematiquement impossibles.

Distinct d'une detection d'anomalie STATISTIQUE (valeur extreme mais
possible, voir src/evaluation/temporal_drift.py) : ici, la valeur viole une
IDENTITE MATHEMATIQUE ou une loi physique universelle - donc jamais
correcte, quel que soit le capteur ou le contexte. Complementaire du
registre d'unites (src/data/units.py) : units.py normalise le REFERENTIEL
(quelle unite), ce module verifie la COHERENCE (la valeur a-t-elle un sens
dans son unite).

Regle "0 mock" appliquee : chaque borne est une identite mathematique
VERIFIEE contre la formule reellement utilisee dans le code
(src/features/time_domain.py), jamais une borne "raisonnable" devinee. Une
borne qui necessiterait une donnee constructeur non disponible (ex. plage
de mesure exacte de l'accelerometre PCB 336C04 - non documentee meme dans
data/raw/paderborn/K001/measuring_log_K001.pdf, seule la sensibilite
100 mV/g y figure, pas la plage) est explicitement ABSENTE plutot que
devinee. Voir docs/known_issues.md si cette plage est confirmee un jour.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Tolerance numerique (bruit d'arrondi float64) - une valeur legerement sous
# la borne theorique (ex. 0.999999998 pour un crest_factor) n'est pas un
# signal impossible, juste de l'arithmetique flottante.
_FLOAT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class PlausibilityBound:
    min_value: float
    reason: str  # doit citer la formule/l'identite exacte, pas une generalite


# Bornes mathematiques UNIVERSELLES, verifiees contre les formules reelles de
# src/features/time_domain.py - valables quel que soit le capteur/la source,
# aucune donnee constructeur necessaire.
UNIVERSAL_BOUNDS: dict[str, PlausibilityBound] = {
    "rms": PlausibilityBound(
        min_value=0.0,
        reason="RMS = sqrt(mean(x^2)) est une racine carree, toujours >= 0.",
    ),
    "peak_to_peak": PlausibilityBound(
        min_value=0.0,
        reason="peak_to_peak = max(x) - min(x), toujours >= 0 par definition.",
    ),
    "crest_factor": PlausibilityBound(
        min_value=1.0,
        reason=(
            "crest_factor = max(|x|)/RMS (src/features/time_domain.py::crest_factor). "
            "Identite : RMS^2 = mean(x^2) <= max(x^2) = max(|x|)^2, donc max(|x|) >= RMS "
            "toujours - crest_factor < 1 est mathematiquement impossible pour cette formule."
        ),
    ),
    "kurtosis": PlausibilityBound(
        min_value=1.0,
        reason=(
            "kurtosis (convention Pearson non-excedentaire, fisher=False, voir "
            "src/features/time_domain.py::kurtosis - gaussien -> 3). Inegalite de "
            "Pearson : kurtosis >= skewness^2 + 1 >= 1 pour toute distribution reelle "
            "a moment d'ordre 4 fini. kurtosis < 1 est mathematiquement impossible."
        ),
    ),
}


@dataclass(frozen=True)
class PlausibilityViolation:
    feature_name: str
    value: float
    bound: PlausibilityBound


def check_plausibility(feature_name: str, value: float) -> PlausibilityViolation | None:
    """Retourne une violation si `value` est mathematiquement impossible pour
    `feature_name`, None sinon (y compris si `feature_name` n'a pas de borne
    universelle definie - PAS une absence de probleme confirmee, juste hors
    du perimetre couvert ici)."""
    bound = UNIVERSAL_BOUNDS.get(feature_name)
    if bound is None:
        return None
    if value < bound.min_value - _FLOAT_TOLERANCE:
        return PlausibilityViolation(feature_name=feature_name, value=value, bound=bound)
    return None


def scan_dataframe(
    df: pd.DataFrame, feature_col: str = "feature_name", value_col: str = "value"
) -> pd.DataFrame:
    """Applique check_plausibility a chaque ligne d'un DataFrame long-format
    (meme structure que la table `feature` EAV du projet). Retourne
    UNIQUEMENT les violations trouvees - DataFrame vide (pas un placeholder)
    si tout est plausible, comportement honnete coherent avec la regle
    "0 mock" (afficher l'absence de probleme plutot que l'inventer)."""
    if df.empty:
        return pd.DataFrame(columns=[feature_col, value_col, "raison", "borne_min"])

    other_cols = [c for c in df.columns if c not in (feature_col, value_col)]
    rows = []
    for _, row in df.iterrows():
        v = check_plausibility(row[feature_col], row[value_col])
        if v is not None:
            rows.append(
                {
                    feature_col: v.feature_name,
                    value_col: v.value,
                    "raison": v.bound.reason,
                    "borne_min": v.bound.min_value,
                    **{c: row[c] for c in other_cols},
                }
            )
    return pd.DataFrame(rows)
