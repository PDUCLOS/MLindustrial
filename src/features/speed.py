"""Detection vitesse fixe/variable a partir d'un canal tachymetrique mesure
(pas d'estimation par order-tracking depuis la vibration seule - implemente
seulement quand une source sans canal vitesse dedie l'exigera).

Complementaire d'un input manuel (rpm/Hz saisi par l'utilisateur quand aucun
canal vitesse n'est disponible, ex. XJTU-SY) - voir TestSession.rotational_speed_rpm
pour la valeur nominale/config, ce module pour la valeur reelle mesuree quand
elle existe.
"""

import numpy as np

# Coefficient de variation (std/mean) au-dela duquel on considere la vitesse
# comme variable plutot que fixe. Choisi empiriquement : sur Paderborn (vitesse
# nominale fixe par design), le CV mesure est de l'ordre de 1e-4 (voir
# docs/known_issues.md ou docs/data_model.md pour le detail) - un seuil a 1%
# laisse une marge large avant de declencher un faux positif "vitesse variable".
DEFAULT_VARIABLE_SPEED_CV_THRESHOLD = 0.01


def mean_speed_rpm(speed_signal: np.ndarray) -> float:
    return float(np.mean(speed_signal))


def speed_coefficient_of_variation(speed_signal: np.ndarray) -> float:
    mean = np.mean(speed_signal)
    if mean == 0:
        return 0.0
    return float(np.std(speed_signal) / abs(mean))


def is_variable_speed(speed_signal: np.ndarray, cv_threshold: float = DEFAULT_VARIABLE_SPEED_CV_THRESHOLD) -> bool:
    """True si le coefficient de variation de la vitesse mesuree depasse le seuil."""
    return speed_coefficient_of_variation(speed_signal) > cv_threshold


def speed_features(speed_signal: np.ndarray) -> dict[str, float]:
    return {
        "mean_rpm": mean_speed_rpm(speed_signal),
        "speed_cv": speed_coefficient_of_variation(speed_signal),
        "is_variable_speed": float(is_variable_speed(speed_signal)),
    }
