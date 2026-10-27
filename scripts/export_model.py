"""Exporte le modele servi par l'API (api/main.py) + des mesures de demo.

1. Recalcule la validation croisee Phase 2 (vibration seule, 5 folds groupes
   par roulement) avec le code de scripts/run_gbm.py -> metriques du model card.
2. Reentraine le meme XGBoost sur tous les roulements SAUF 3 roulements tenus
   a l'ecart (1 sain, 1 defaut artificiel, 1 defaut reel, choisis avant tout
   resultat) : les mesures de demo de l'API sont donc hors entrainement.
3. Ecrit models/gbm_vibration.json, models/model_card.json,
   models/demo_samples.npz (signaux int16 + facteur d'echelle : le capteur
   Paderborn est numerise sur 16 bits, la conversion est sans perte).

Usage : uv run python scripts/export_model.py   (DATABASE_URL requis)
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_gbm import cross_validate_sensor_set, load_wide_features
from src.data.dataset_hash import hash_directory
from src.data.db import get_engine
from src.models.baseline import fit_threshold
from src.models.gbm import train_gbm
from src.serving.predictor import FEATURE_ORDER, PADERBORN_SAMPLING_RATE_HZ

HELD_OUT = {"K006": "healthy", "KI08": "artificial", "KA22": "real"}
DEMO_CONDITIONS = ["N15_M07_F10", "N09_M07_F10"]
ADC_STEP = 100 / 32768  # pas de quantification mesure sur les signaux Paderborn
MODEL_DIR = ROOT / "models"
PROCESSED = ROOT / "data" / "processed" / "paderborn"


def main() -> None:
    engine = get_engine()
    df = load_wide_features(engine)
    codes = pd.read_sql("select id as asset_id, code from asset", engine)
    df = df.merge(codes, on="asset_id")

    cv = cross_validate_sensor_set(df, "vibration_only", ["vibration"])
    print(f"CV 5 folds vibration seule : F1 macro {cv['f1_macro_mean']:.3f} +/- {cv['f1_macro_std']:.3f}")

    train = df[~df["code"].isin(HELD_OUT)]
    X, y = train[FEATURE_ORDER].to_numpy(), train["label"].to_numpy()
    model = train_gbm(X, y)
    baseline = fit_threshold(train["vibration_kurtosis"].to_numpy(), y)

    MODEL_DIR.mkdir(exist_ok=True)
    model.save_model(str(MODEL_DIR / "gbm_vibration.json"))

    meta, arrays = [], {}
    for code, origin in HELD_OUT.items():
        for cond in DEMO_CONDITIONS:
            path = PROCESSED / code / f"{cond}_1.parquet"
            v = pd.read_parquet(path, columns=["vibration"])["vibration"].to_numpy()
            q = np.round(v / ADC_STEP)
            assert np.allclose(q * ADC_STEP, v, atol=1e-9), "signal non quantifie sur 16 bits"
            sid = f"{code}_{cond}"
            arrays[sid] = q.astype(np.int16)
            meta.append({
                "id": sid, "bearing": code, "condition": cond, "origin": origin,
                "truth": "healthy" if origin == "healthy" else "faulty",
                "scale": ADC_STEP, "seen_in_training": False,
            })
    np.savez_compressed(MODEL_DIR / "demo_samples.npz", meta=json.dumps(meta), **arrays)

    card = {
        "model_name": "xgboost_vibration_time_domain",
        "task": "health_state binaire (healthy / faulty), roulement 6203, banc Paderborn KAt",
        "feature_order": FEATURE_ORDER,
        "sampling_rate_hz": PADERBORN_SAMPLING_RATE_HZ,
        "xgboost_params": {k: v for k, v in model.get_params().items()
                           if k in ("n_estimators", "max_depth", "learning_rate")},
        "trained_on": {
            "n_measurements": int(len(train)),
            "n_bearings": int(train["code"].nunique()),
            "held_out_bearings": HELD_OUT,
        },
        "cv_vibration_only_32_bearings": {
            "scheme": "StratifiedGroupKFold 5 folds, groupe = roulement, random_state=42",
            "f1_macro_mean": round(cv["f1_macro_mean"], 4),
            "f1_macro_std": round(cv["f1_macro_std"], 4),
            "balanced_accuracy_mean": round(cv["balanced_accuracy_mean"], 4),
            "fold_f1": [round(f, 4) for f in cv["fold_f1"]],
        },
        "baseline_kurtosis": {"threshold": round(baseline["threshold"], 4),
                              "direction": baseline["direction"]},
        "dataset_hash": hash_directory(ROOT / "data" / "processed"),
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "license_data": "Paderborn KAt-DataCenter, CC BY-NC 4.0 (Lessmeier et al., 2016)",
    }
    (MODEL_DIR / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False),
                                               encoding="utf-8")
    print(f"Exporte : {len(train)} mesures / {train['code'].nunique()} roulements, "
          f"{len(meta)} mesures de demo hors entrainement.")


if __name__ == "__main__":
    main()
