"""Baseline seuil (RMS ou kurtosis brut) - a battre franchement par le GBM
avant de le preferer (docs/brief_projet.md section 4, regle 4)."""

import numpy as np
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score


def fit_threshold(train_values: np.ndarray, train_labels: np.ndarray, direction: str = "auto") -> dict:
    """Seuil (choisi sur TRAIN uniquement) qui maximise le F1 macro.

    train_labels : binaire, 1 = faulty. direction : 'higher_is_faulty',
    'lower_is_faulty', ou 'auto' (teste les deux sens, garde le meilleur SUR
    TRAIN - le sens n'est pas suppose a priori, voir docs/known_issues.md ou
    la kurtosis brute s'est averee inversement correlee au defaut)."""
    candidates = np.unique(train_values)
    directions = ["higher_is_faulty", "lower_is_faulty"] if direction == "auto" else [direction]
    best = {"threshold": None, "direction": None, "f1_macro_train": -np.inf}

    for d in directions:
        for t in candidates:
            pred = apply_threshold(train_values, t, d)
            score = f1_score(train_labels, pred, average="macro", zero_division=0)
            if score > best["f1_macro_train"]:
                best = {"threshold": float(t), "direction": d, "f1_macro_train": float(score)}
    return best


def apply_threshold(values: np.ndarray, threshold: float, direction: str) -> np.ndarray:
    if direction == "higher_is_faulty":
        return (values >= threshold).astype(int)
    if direction == "lower_is_faulty":
        return (values <= threshold).astype(int)
    raise ValueError(f"direction inconnue : {direction!r}")


def evaluate(true_labels: np.ndarray, pred_labels: np.ndarray) -> dict:
    cm = confusion_matrix(true_labels, pred_labels, labels=[0, 1])
    return {
        "f1_macro": float(f1_score(true_labels, pred_labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(true_labels, pred_labels)),
        "confusion_matrix": cm.tolist(),  # [[TN, FP], [FN, TP]]
    }
