"""Gradient boosting intra-condition + comparaison vibration-seule / courant-seul
/ fusion (docs/brief_projet.md Phase 2 + objectif secondaire section 2).

IMPORTANT : avec seulement 32 roulements, un seul split train/test est trop
bruite pour conclure quoi que ce soit (teste : sur 5 seeds, le "gagnant" entre
vibration/courant/fusion change a chaque fois - voir docs/results_phase2.md).
Validation croisee GroupKFold (groupe = asset_id, jamais de fuite inter-fold)
et moyenne +/- ecart-type sur les folds, pas un chiffre unique.

Usage : uv run python scripts/run_gbm.py
"""

import sys
from pathlib import Path

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.dataset_hash import hash_directory
from src.data.db import get_engine
from src.data.splits import assert_no_asset_leakage
from src.models.gbm import evaluate, train_gbm

N_FOLDS = 5
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
FEATURE_NAMES = ["rms", "peak_to_peak", "crest_factor", "kurtosis", "skewness"]

SENSOR_SETS = {
    "vibration_only": ["vibration"],
    "current_only": ["current_1", "current_2"],
    "fusion": ["vibration", "current_1", "current_2"],
}


def load_wide_features(engine) -> pd.DataFrame:
    df = pd.read_sql(
        """
        select s.asset_id, s.test_session_id, s.measurement_index, s.channel,
               a.health_state, f.feature_name, f.value
        from feature f
        join signal s on s.id = f.signal_id
        join asset a on a.id = s.asset_id
        where f.feature_name = ANY(%(names)s)
        """,
        engine,
        params={"names": FEATURE_NAMES},
    )
    df["col"] = df["channel"] + "_" + df["feature_name"]
    wide = df.pivot_table(
        index=["asset_id", "test_session_id", "measurement_index", "health_state"],
        columns="col", values="value",
    ).reset_index()
    wide["label"] = (wide["health_state"] == "faulty").astype(int)
    return wide


def _feature_columns(df: pd.DataFrame, channels: list[str]) -> list[str]:
    return [c for c in df.columns if any(c.startswith(ch + "_") for ch in channels)]


def cross_validate_sensor_set(df: pd.DataFrame, name: str, channels: list[str]) -> dict:
    cols = _feature_columns(df, channels)
    groups = df["asset_id"].to_numpy()
    X = df[cols].to_numpy()
    y = df["label"].to_numpy()

    gkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    fold_f1, fold_bacc = [], []
    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]
        assert_no_asset_leakage(train_df, test_df, asset_col="asset_id")

        model = train_gbm(X[train_idx], y[train_idx])
        metrics = evaluate(model, X[test_idx], y[test_idx])
        fold_f1.append(metrics["f1_macro"])
        fold_bacc.append(metrics["balanced_accuracy"])

    return {
        "sensor_set": name,
        "n_features": len(cols),
        "f1_macro_mean": float(np.mean(fold_f1)),
        "f1_macro_std": float(np.std(fold_f1)),
        "balanced_accuracy_mean": float(np.mean(fold_bacc)),
        "balanced_accuracy_std": float(np.std(fold_bacc)),
        "fold_f1": fold_f1,
    }


def main() -> None:
    engine = get_engine()
    df = load_wide_features(engine)
    n_assets = df["asset_id"].nunique()
    print(f"{len(df)} mesures, {n_assets} assets, {N_FOLDS}-fold GroupKFold (groupe=asset_id).")

    dataset_hash = hash_directory(PROCESSED_DIR)
    print(f"dataset hash (data/processed/**/*.parquet) : {dataset_hash[:16]}...")

    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("gbm_sensor_comparison_cv")

    results = []
    for name, channels in SENSOR_SETS.items():
        result = cross_validate_sensor_set(df, name, channels)
        results.append(result)
        with mlflow.start_run(run_name=f"gbm_cv_{name}"):
            mlflow.log_param("sensor_set", name)
            mlflow.log_param("channels", ",".join(channels))
            mlflow.log_param("n_features", result["n_features"])
            mlflow.log_param("n_folds", N_FOLDS)
            mlflow.log_param("dataset_hash", dataset_hash)
            mlflow.log_metric("f1_macro_mean", result["f1_macro_mean"])
            mlflow.log_metric("f1_macro_std", result["f1_macro_std"])
            mlflow.log_metric("balanced_accuracy_mean", result["balanced_accuracy_mean"])
            mlflow.log_text(f"F1 macro par fold : {result['fold_f1']}", "fold_scores.txt")

            # Modele final : re-entraine sur TOUTES les donnees disponibles
            # (les 5 modeles de la CV ci-dessus servent a EVALUER, pas a etre
            # deployes - ils n'ont chacun vu que 80% des donnees). Logue pour
            # que le meilleur sensor_set soit rechargeable plutot que perdu a
            # la fin du process (voir docs/feature_backlog.md F-44/F-45).
            cols = _feature_columns(df, channels)
            final_model = train_gbm(df[cols].to_numpy(), df["label"].to_numpy())
            mlflow.xgboost.log_model(final_model, name="model", input_example=df[cols].head(3))
        print(
            f"[{name}] n_features={result['n_features']} "
            f"F1_macro = {result['f1_macro_mean']:.3f} +/- {result['f1_macro_std']:.3f} "
            f"(folds: {[round(f, 3) for f in result['fold_f1']]})"
        )

    print("\n--- Comparaison (moyenne CV, pas un split unique) ---")
    # meilleure feature baseline (kurtosis, CV StratifiedGroupKFold), voir scripts/run_baseline.py
    baseline_f1, baseline_std = 0.682, 0.158
    for r in sorted(results, key=lambda r: -r["f1_macro_mean"]):
        lo, hi = r["f1_macro_mean"] - r["f1_macro_std"], r["f1_macro_mean"] + r["f1_macro_std"]
        baseline_lo, baseline_hi = baseline_f1 - baseline_std, baseline_f1 + baseline_std
        overlap = lo <= baseline_hi and baseline_lo <= hi
        verdict = "chevauche la baseline (pas de gain net demontre)" if overlap else (
            "bat la baseline" if r["f1_macro_mean"] > baseline_f1 else "sous la baseline"
        )
        print(f"  {r['sensor_set']}: {r['f1_macro_mean']:.3f} +/- {r['f1_macro_std']:.3f} -> {verdict}")


if __name__ == "__main__":
    main()
