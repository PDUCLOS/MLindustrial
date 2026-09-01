"""Frequences caracteristiques de defaut roulement (voir docs/brief_projet.md section 5).

n = nombre de billes, fr = frequence de rotation (Hz), d = diametre bille (mm),
D = diametre primitif (mm), phi = angle de contact (degres).
"""

import math


def _geometry_factor(d_mm: float, big_d_mm: float, phi_deg: float) -> float:
    return (d_mm / big_d_mm) * math.cos(math.radians(phi_deg))


def rotational_frequency_hz(rpm: float) -> float:
    return rpm / 60.0


def bpfo(n_balls: int, fr_hz: float, d_mm: float, big_d_mm: float, phi_deg: float = 0.0) -> float:
    """Ball Pass Frequency Outer race - defaut bague exterieure."""
    return (n_balls / 2) * fr_hz * (1 - _geometry_factor(d_mm, big_d_mm, phi_deg))


def bpfi(n_balls: int, fr_hz: float, d_mm: float, big_d_mm: float, phi_deg: float = 0.0) -> float:
    """Ball Pass Frequency Inner race - defaut bague interieure."""
    return (n_balls / 2) * fr_hz * (1 + _geometry_factor(d_mm, big_d_mm, phi_deg))


def bsf(n_balls: int, fr_hz: float, d_mm: float, big_d_mm: float, phi_deg: float = 0.0) -> float:
    """Ball Spin Frequency - defaut bille."""
    factor = _geometry_factor(d_mm, big_d_mm, phi_deg)
    return (big_d_mm / (2 * d_mm)) * fr_hz * (1 - factor**2)


def ftf(n_balls: int, fr_hz: float, d_mm: float, big_d_mm: float, phi_deg: float = 0.0) -> float:
    """Fundamental Train Frequency - defaut cage. n_balls non utilise, garde
    dans la signature pour homogeneite d'appel avec bpfo/bpfi/bsf."""
    del n_balls
    return (fr_hz / 2) * (1 - _geometry_factor(d_mm, big_d_mm, phi_deg))


def all_fault_frequencies(
    n_balls: int, rpm: float, d_mm: float, big_d_mm: float, phi_deg: float = 0.0
) -> dict[str, float]:
    fr = rotational_frequency_hz(rpm)
    return {
        "BPFO": bpfo(n_balls, fr, d_mm, big_d_mm, phi_deg),
        "BPFI": bpfi(n_balls, fr, d_mm, big_d_mm, phi_deg),
        "BSF": bsf(n_balls, fr, d_mm, big_d_mm, phi_deg),
        "FTF": ftf(n_balls, fr, d_mm, big_d_mm, phi_deg),
    }


def mains_separation_hz(
    n_balls: int,
    rpm: float,
    d_mm: float,
    big_d_mm: float,
    phi_deg: float = 0.0,
    mains_hz: float = 50.0,
    n_harmonics: int = 4,
    n_shaft_orders: int = 3,
) -> float:
    """Ecart (Hz) entre la raie la plus proche (frequences de defaut + ordres
    arbre 1x/2x/3x) et l'harmonique secteur la plus proche.

    Sert a choisir une vitesse de banc qui ne fait pas coincider une raie
    diagnostique avec le secteur EU (50/100/150/200 Hz) - ne resout PAS la
    proximite structurelle BPFO~3x/BSF~2x qui est un ordre (independant de la
    vitesse), voir docs/theorie_reference.md. A 1500 tr/min sur un roulement
    6203 Paderborn, 2x = 50.0 Hz exactement (ecart nul, collision totale)."""
    fr = rotational_frequency_hz(rpm)
    freqs = all_fault_frequencies(n_balls, rpm, d_mm, big_d_mm, phi_deg)
    lines = list(freqs.values()) + [k * fr for k in range(1, n_shaft_orders + 1)]
    mains_lines = [k * mains_hz for k in range(1, n_harmonics + 1)]
    return min(abs(line - m) for line in lines for m in mains_lines)
