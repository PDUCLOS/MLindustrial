"""Indicateurs temporels standards (voir docs/brief_projet.md section 5)."""

import numpy as np
from scipy import stats


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def peak_to_peak(x: np.ndarray) -> float:
    return float(np.max(x) - np.min(x))


def crest_factor(x: np.ndarray) -> float:
    x_rms = rms(x)
    if x_rms == 0:
        return 0.0
    return float(np.max(np.abs(x)) / x_rms)


def kurtosis(x: np.ndarray) -> float:
    """Convention vibratoire : gaussien -> 3 (fisher=False, pas de kurtosis d'exces)."""
    return float(stats.kurtosis(x, fisher=False))


def skewness(x: np.ndarray) -> float:
    return float(stats.skew(x))


def time_domain_features(x: np.ndarray) -> dict[str, float]:
    return {
        "rms": rms(x),
        "peak_to_peak": peak_to_peak(x),
        "crest_factor": crest_factor(x),
        "kurtosis": kurtosis(x),
        "skewness": skewness(x),
    }
