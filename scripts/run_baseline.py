"""Baseline seuil RMS/kurtosis (docs/brief_projet.md Phase 2). Split par asset (jamais par
signal), evaluation intra-condition, F1 macro + balanced accuracy (classes
desequilibrees : ~480 sains / ~2079 defauts).

Validation croisee StratifiedGroupKFold (groupe=asset_id) : avec 32 roulements,
un seul split est trop bruite pour conclure (voir scripts/run_gbm.py, meme
constat mesure sur le GBM - moyenne +/- ecart-type sur les folds, pas un
chiffre unique.

Usage : uv run python scripts/run_baseline.py
"""

import os
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset_hash import hash_directory
from src.data.db import get_engine
from src.data.splits import assert_no_asset_leakage
from src.models.baseline import apply_threshold, evaluate, fit_threshold

FEATURES_TO_TRY = ["rms", "kurtosis", "crest_factor"]
N_FOLDS = 5
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def load_features(engine) -> pd.DataFrame:
    df = pd.read_sql(
        """
        select f.asset_id, f.signal_id, a.health_state, f.feature_name, f.value
        from feature f
        join asset a on a.id = f.asset_id
        where f.channel = 'vibration' and f.feature_name = ANY(%(names)s)
        """,
        engine,
        params={"names": FEATURES_TO_TRY},
    )
    wide = df.pivot_table(
        index=["asset_id", "signal_id", "health_state"], columns="feature_name", values="value"
    ).reset_index()
    wide["label"] = (wide["health_state"] == "faulty").astype(int)
    return wide


def cross_validate_feature(df: pd.DataFrame, feature: str) -> dict:
    groups = df["asset_id"].to_numpy()
    values = df[feature].to_numpy()
    labels = df["label"].to_numpy()

    gkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    fold_f1, fold_bacc, thresholds, directions = [], [], [], []

    for train_idx, test_idx in gkf.split(values, labels, groups=groups):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]
        assert_no_asset_leakage(train_df, test_df, asset_col="asset_id")

        fit = fit_threshold(values[train_idx], labels[train_idx])
        pred = apply_threshold(values[test_idx], fit["threshold"], fit["direction"])
        metrics = evaluate(labels[test_idx], pred)

        fold_f1.append(metrics["f1_macro"])
        fold_bacc.append(metrics["balanced_accuracy"])
        thresholds.append(fit["threshold"])
        directions.append(fit["direction"])

    return {
        "feature": feature,
        "f1_macro_mean": float(np.mean(fold_f1)),
        "f1_macro_std": float(np.std(fold_f1)),
        "balanced_accuracy_mean": float(np.mean(fold_bacc)),
        "balanced_accuracy_std": float(np.std(fold_bacc)),
        "fold_f1": fold_f1,
        "directions": directions,
        "thresholds": thresholds,
    }


def main() -> None:
    engine = get_engine()
    df = load_features(engine)
    print(f"{len(df)} mesures (vibration), {df['asset_id'].nunique()} assets, {N_FOLDS}-fold CV.")

    dataset_hash = hash_directory(PROCESSED_DIR)
    print(f"dataset hash (data/processed/**/*.parquet) : {dataset_hash[:16]}...")

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    mlflow.set_experiment("baseline_threshold_cv")

    results = []
    for feature in FEATURES_TO_TRY:
        result = cross_validate_feature(df, feature)
        results.append(result)

        # Seuil FINAL : re-entraine sur 100% des donnees (la CV ci-dessus sert a
        # EVALUER la stabilite, pas a produire un seuil deployable - 5 folds =
        # 5 seuils differents, aucun n'est "le" seuil. Meme pattern que le refit
        # final des modeles GBM (scripts/run_gbm.py). Sans ce refit, aucun seuil
        # unique n'est loggue en param mlflow -> le dashboard n'aurait rien de
        # reel a lire (regle "0 mock" - un seuil invente en fallback est
        # explicitement interdit).
        final_fit = fit_threshold(df[feature].to_numpy(), df["label"].to_numpy())

        with mlflow.start_run(run_name=f"threshold_cv_{feature}"):
            mlflow.log_param("feature", feature)
            mlflow.log_param("n_folds", N_FOLDS)
            mlflow.log_param("dataset_hash", dataset_hash)
            mlflow.log_param("final_threshold", final_fit["threshold"])
            mlflow.log_param("final_direction", final_fit["direction"])
            mlflow.log_metric("f1_macro_mean", result["f1_macro_mean"])
            mlflow.log_metric("f1_macro_std", result["f1_macro_std"])
            mlflow.log_metric("balanced_accuracy_mean", result["balanced_accuracy_mean"])
            mlflow.log_metric("f1_macro_train_on_full_data", final_fit["f1_macro_train"])
            mlflow.log_text(
                f"F1 macro par fold : {result['fold_f1']}\n"
                f"directions par fold : {result['directions']}\n"
                f"seuils par fold : {result['thresholds']}\n"
                f"seuil final (100% donnees) : {final_fit['threshold']} ({final_fit['direction']})",
                "fold_details.txt",
            )
        print(
            f"[{feature}] F1_macro = {result['f1_macro_mean']:.3f} +/- {result['f1_macro_std']:.3f} "
            f"(folds: {[round(f, 3) for f in result['fold_f1']]}, directions: {set(result['directions'])})"
        )

    best = max(results, key=lambda r: r["f1_macro_mean"])
    print(f"\nMeilleure feature baseline (moyenne CV) : {best['feature']} (F1 macro = {best['f1_macro_mean']:.3f} +/- {best['f1_macro_std']:.3f})")


if __name__ == "__main__":
    main()
