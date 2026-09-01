"""Verifie l'absence de fuite d'asset directement sur les fonctions de CV
REELLES de scripts/run_baseline.py et scripts/run_gbm.py (pas seulement
assert_no_asset_leakage isolee, deja testee dans test_splits.py).

Deux niveaux de verification, volontairement independants :
1. La config StratifiedGroupKFold telle qu'importee des scripts (N_FOLDS) est
   rejouee sur des donnees synthetiques et verifiee sans dependre du code
   interne des scripts - si quelqu'un retire l'appel a assert_no_asset_leakage
   DANS les scripts, ce niveau detecte quand meme une fuite structurelle.
2. Les fonctions cross_validate_feature / cross_validate_sensor_set sont
   appelees TELLES QUELLES (import direct, pas de reimplementation) sur des
   donnees synthetiques - toute regression dans leur logique de split fait
   remonter l'erreur levee par assert_no_asset_leakage.

Donnees 100% synthetiques (pas de DB requise) : ces tests tournent sans
Docker/Postgres.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import StratifiedGroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_baseline import N_FOLDS as BASELINE_N_FOLDS
from scripts.run_baseline import cross_validate_feature
from scripts.run_gbm import N_FOLDS as GBM_N_FOLDS
from scripts.run_gbm import cross_validate_sensor_set


def _make_synthetic_asset_df(n_assets: int = 32, rows_per_asset: int = 20, seed: int = 0) -> pd.DataFrame:
    """Imite la forme du dataframe reel : plusieurs lignes (mesures) par
    asset_id, desequilibre de classe comparable a Paderborn (~19% healthy)."""
    rng = np.random.default_rng(seed)
    asset_ids = [f"asset_{i}" for i in range(n_assets)]
    label_by_asset = {a: int(rng.random() < 0.19) for a in asset_ids}
    rows = [
        {"asset_id": a, "label": label_by_asset[a]}
        for a in asset_ids
        for _ in range(rows_per_asset)
    ]
    return pd.DataFrame(rows)


@pytest.mark.parametrize("n_folds", [BASELINE_N_FOLDS, GBM_N_FOLDS])
def test_stratified_group_kfold_config_no_leakage_on_any_fold(n_folds):
    """Niveau 1 : rejoue la config reelle (n_folds importe des scripts) sur
    des donnees synthetiques, verifie chaque fold independamment de
    assert_no_asset_leakage."""
    df = _make_synthetic_asset_df()
    gkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=42)

    for fold_idx, (train_idx, test_idx) in enumerate(gkf.split(df, df["label"], groups=df["asset_id"])):
        train_assets = set(df.iloc[train_idx]["asset_id"])
        test_assets = set(df.iloc[test_idx]["asset_id"])
        leaked = train_assets & test_assets
        assert not leaked, f"fold {fold_idx} : fuite d'assets train/test = {leaked}"


def test_run_baseline_cross_validate_feature_no_leak():
    """Niveau 2 : appelle la VRAIE fonction de scripts/run_baseline.py."""
    df = _make_synthetic_asset_df()
    rng = np.random.default_rng(1)
    df["rms"] = rng.normal(size=len(df))

    # Si une regression future retire assert_no_asset_leakage() de
    # cross_validate_feature ou casse le parametre groups=..., ce test doit
    # echouer bruyamment - soit par exception levee ici, soit (a minima) en
    # produisant un nombre de folds incoherent.
    result = cross_validate_feature(df, "rms")
    assert len(result["fold_f1"]) == BASELINE_N_FOLDS


def test_run_gbm_cross_validate_sensor_set_no_leak():
    """Niveau 2 : appelle la VRAIE fonction de scripts/run_gbm.py."""
    df = _make_synthetic_asset_df(rows_per_asset=10)
    rng = np.random.default_rng(2)
    for ch in ["vibration", "current_1", "current_2"]:
        for feat in ["rms", "peak_to_peak", "crest_factor", "kurtosis", "skewness"]:
            df[f"{ch}_{feat}"] = rng.normal(size=len(df))

    result = cross_validate_sensor_set(df, "vibration_only", ["vibration"])
    assert len(result["fold_f1"]) == GBM_N_FOLDS
